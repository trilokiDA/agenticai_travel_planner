import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ResilientLLM:
    """
    A transparent LLM wrapper that adds smart retry and fallback logic.

    Behaviour:
        - 503 UNAVAILABLE  → transient server overload, retry with exponential back-off
        - 429 RESOURCE_EXHAUSTED (daily quota) → quota hard-limit hit, skip retries
          and fall back to the backup provider immediately
        - 429 (rate limit / per-minute) → wait the suggested delay, then retry
        - Any other error  → re-raise immediately (no silent swallowing)

    The wrapper is fully transparent: it exposes .invoke() so it can be used
    anywhere a normal LangChain chat model is used.
    """

    def __init__(self, primary, fallback=None, max_retries: int = 3):
        self.primary = primary
        self.fallback = fallback
        self.max_retries = max_retries

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_quota_exhausted(exc: Exception) -> bool:
        """True when the daily free-tier quota is fully consumed."""
        msg = str(exc)
        return (
            "RESOURCE_EXHAUSTED" in msg
            and (
                "GenerateRequestsPerDay" in msg   # daily quota violation
                or "free_tier" in msg
            )
        )

    @staticmethod
    def _is_rate_limited(exc: Exception) -> bool:
        """True for per-minute rate-limit 429s (retryable after a short wait)."""
        msg = str(exc)
        return "RESOURCE_EXHAUSTED" in msg or "429" in msg

    @staticmethod
    def _is_unavailable(exc: Exception) -> bool:
        """True for transient 503 / 502 / 504 server errors."""
        msg = str(exc)
        return "UNAVAILABLE" in msg or "503" in msg or "502" in msg or "504" in msg

    @staticmethod
    def _parse_retry_delay(exc: Exception, default: float = 5.0) -> float:
        """
        Extract the suggested retry delay from the error message if present
        (e.g. 'Please retry in 38.9s'), otherwise fall back to default.
        """
        import re
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
        return float(match.group(1)) if match else default

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def invoke(self, prompt):
        last_exc = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return self.primary.invoke(prompt)

            except Exception as exc:
                last_exc = exc

                if self._is_quota_exhausted(exc):
                    # Hard daily limit — retrying is pointless
                    print(
                        f"[LLM] Gemini daily quota exhausted. "
                        f"Switching to fallback immediately."
                    )
                    break  # exit retry loop → use fallback

                elif self._is_unavailable(exc):
                    # Transient server overload — exponential back-off
                    wait = min(2 ** attempt, 30)
                    print(
                        f"[LLM] Gemini unavailable (503). "
                        f"Retrying in {wait}s (attempt {attempt}/{self.max_retries})…"
                    )
                    time.sleep(wait)

                elif self._is_rate_limited(exc):
                    # Per-minute rate limit — honour the suggested delay
                    wait = self._parse_retry_delay(exc, default=60.0)
                    if attempt < self.max_retries:
                        print(
                            f"[LLM] Gemini rate-limited (429). "
                            f"Waiting {wait:.0f}s (attempt {attempt}/{self.max_retries})…"
                        )
                        time.sleep(wait)
                    else:
                        print("[LLM] Gemini rate-limit retries exhausted. Switching to fallback.")
                        break

                else:
                    # Unknown / non-retryable error — surface it immediately
                    raise

        # ── Fallback ──────────────────────────────────────────────────── #
        if self.fallback:
            print("[LLM] Using fallback provider (Groq).")
            return self.fallback.invoke(prompt)

        # No fallback available — raise the last captured exception
        raise last_exc  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────── #
#  Builder helpers                                                          #
# ──────────────────────────────────────────────────────────────────────── #

def _build_groq():
    """Return a ChatGroq instance using GROQ_API_KEY."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set in your .env file. "
            "Please add it or switch LLM_PROVIDER to 'gemini'."
        )
    from langchain_groq import ChatGroq
    print("[LLM Factory] Using provider: Groq")
    return ChatGroq(
        model="openai/gpt-oss-20b",
        api_key=api_key
    )


def _build_gemini():
    """Return a ChatGoogleGenerativeAI instance using GOOGLE_API_KEY."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set in your .env file. "
            "Please add it or switch LLM_PROVIDER to 'groq'."
        )
    from langchain_google_genai import ChatGoogleGenerativeAI
    print("[LLM Factory] Using provider: Gemini")
    return ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        google_api_key=api_key
    )


# ──────────────────────────────────────────────────────────────────────── #
#  Public entry point                                                       #
# ──────────────────────────────────────────────────────────────────────── #

def get_llm():
    """
    Factory function that returns an LLM instance based on the LLM_PROVIDER
    environment variable. Defaults to 'groq' if not set.

    Supported providers:
        - "groq"   : Uses ChatGroq with GROQ_API_KEY
        - "gemini" : Uses ChatGoogleGenerativeAI with GOOGLE_API_KEY,
                     wrapped in ResilientLLM for smart retry + Groq fallback

    .env knobs:
        LLM_PROVIDER            "groq" | "gemini"  (default: "groq")
        LLM_MAX_RETRIES         int                 (default: 3)
        GEMINI_FALLBACK_TO_GROQ "true" | "false"   (default: "true")

    Raises:
        ValueError: If an unsupported LLM_PROVIDER value is specified.
        EnvironmentError: If the required API key for the selected provider is missing.
    """
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
    fallback_enabled = os.getenv("GEMINI_FALLBACK_TO_GROQ", "true").strip().lower() == "true"

    if provider == "groq":
        return _build_groq()

    elif provider == "gemini":
        gemini = _build_gemini()
        fallback = None

        if fallback_enabled:
            try:
                fallback = _build_groq()
                print(
                    f"[LLM Factory] Groq fallback enabled "
                    f"(quota exhaustion / {max_retries} retries → Groq)."
                )
            except EnvironmentError:
                print("[LLM Factory] Groq fallback skipped (no GROQ_API_KEY).")

        return ResilientLLM(primary=gemini, fallback=fallback, max_retries=max_retries)

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: '{provider}'. "
            "Valid options are: 'groq', 'gemini'."
        )
