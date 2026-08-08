"""
weather_engine.py
-----------------
Fetches weather forecast (or historical climate averages) for a destination
using Open-Meteo — completely free, no API key required.

Geocoding is done via Nominatim (OpenStreetMap), consistent with map_engine.py.
"""

import json
import time
from datetime import datetime, timedelta, date
from typing import Optional
from urllib.request import urlopen, Request
from urllib.parse import urlencode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WMO_WEATHER_CODES: dict[int, dict] = {
    0:  {"label": "Clear Sky",           "icon": "☀️"},
    1:  {"label": "Mainly Clear",         "icon": "🌤️"},
    2:  {"label": "Partly Cloudy",        "icon": "⛅"},
    3:  {"label": "Overcast",             "icon": "☁️"},
    45: {"label": "Foggy",                "icon": "🌫️"},
    48: {"label": "Icy Fog",              "icon": "🌫️"},
    51: {"label": "Light Drizzle",        "icon": "🌦️"},
    53: {"label": "Drizzle",              "icon": "🌦️"},
    55: {"label": "Heavy Drizzle",        "icon": "🌧️"},
    61: {"label": "Slight Rain",          "icon": "🌧️"},
    63: {"label": "Rain",                 "icon": "🌧️"},
    65: {"label": "Heavy Rain",           "icon": "🌧️"},
    71: {"label": "Slight Snow",          "icon": "🌨️"},
    73: {"label": "Snow",                 "icon": "❄️"},
    75: {"label": "Heavy Snow",           "icon": "❄️"},
    77: {"label": "Snow Grains",          "icon": "❄️"},
    80: {"label": "Slight Showers",       "icon": "🌦️"},
    81: {"label": "Showers",              "icon": "🌧️"},
    82: {"label": "Violent Showers",      "icon": "⛈️"},
    85: {"label": "Snow Showers",         "icon": "🌨️"},
    86: {"label": "Heavy Snow Showers",   "icon": "❄️"},
    95: {"label": "Thunderstorm",         "icon": "⛈️"},
    96: {"label": "Thunderstorm w/ Hail", "icon": "⛈️"},
    99: {"label": "Thunderstorm w/ Hail", "icon": "⛈️"},
}

# Open-Meteo supports forecast up to 16 days. Beyond that, fall back to
# 30-year climate normals from the archive endpoint.
FORECAST_HORIZON_DAYS = 16


def _decode_wmo(code: int) -> tuple[str, str]:
    """Returns (label, icon) for a WMO weather interpretation code."""
    entry = WMO_WEATHER_CODES.get(code, {"label": "Unknown", "icon": "🌡️"})
    return entry["label"], entry["icon"]


def _fetch_url(url: str) -> dict:
    """Tiny HTTP helper that returns parsed JSON."""
    req = Request(url, headers={"User-Agent": "AITravelPlanner/1.0"})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Geocoding (reuses Nominatim, same as map_engine.py)
# ---------------------------------------------------------------------------

def geocode_destination(destination: str) -> Optional[tuple[float, float]]:
    """Returns (lat, lon) for a city name via Nominatim."""
    try:
        params = urlencode({"q": destination, "format": "json", "limit": 1})
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = Request(url, headers={"User-Agent": "AITravelPlanner/1.0"})
        with urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read().decode())
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Climate Normals (fallback for dates beyond 16-day forecast window)
# ---------------------------------------------------------------------------

def _get_climate_normals(lat: float, lon: float, start_date: date, num_days: int) -> list[dict]:
    """
    Fetches 30-year climate normals from Open-Meteo Archive for the same
    calendar window last year, as a proxy when live forecast is unavailable.
    """
    # Use the equivalent window from the previous year
    ref_start = date(start_date.year - 1, start_date.month, start_date.day)
    ref_end = ref_start + timedelta(days=num_days - 1)

    params = urlencode({
        "latitude": lat,
        "longitude": lon,
        "start_date": ref_start.isoformat(),
        "end_date": ref_end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
        "timezone": "auto",
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"

    try:
        data = _fetch_url(url)
        daily = data.get("daily", {})
        times = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        codes = daily.get("weathercode", [])

        days = []
        for i, d_str in enumerate(times):
            code = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
            label, icon = _decode_wmo(code)
            # Map to the actual travel date
            actual_date = start_date + timedelta(days=i)
            days.append({
                "date": actual_date.isoformat(),
                "day_number": i + 1,
                "temp_max_c": round(t_max[i], 1) if i < len(t_max) and t_max[i] is not None else None,
                "temp_min_c": round(t_min[i], 1) if i < len(t_min) and t_min[i] is not None else None,
                "precipitation_mm": round(precip[i], 1) if i < len(precip) and precip[i] is not None else 0.0,
                "weather_label": label,
                "weather_icon": icon,
                "is_forecast": False,   # indicates historical average, not live forecast
            })
        return days
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Live Forecast
# ---------------------------------------------------------------------------

def _get_live_forecast(lat: float, lon: float, start_date: date, num_days: int) -> list[dict]:
    """
    Fetches the 16-day live forecast from Open-Meteo for the requested window.
    Only returns days that fall within the forecast horizon.
    """
    today = date.today()
    forecast_end = today + timedelta(days=FORECAST_HORIZON_DAYS - 1)

    # Clamp the range to what the API can actually provide
    effective_start = max(start_date, today)
    effective_end = min(start_date + timedelta(days=num_days - 1), forecast_end)

    if effective_start > effective_end:
        return []

    params = urlencode({
        "latitude": lat,
        "longitude": lon,
        "forecast_days": FORECAST_HORIZON_DAYS,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
        "timezone": "auto",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"

    try:
        data = _fetch_url(url)
        daily = data.get("daily", {})
        times = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        codes = daily.get("weathercode", [])
        wind = daily.get("windspeed_10m_max", [])

        days = []
        for i, d_str in enumerate(times):
            d = date.fromisoformat(d_str)
            if d < effective_start or d > effective_end:
                continue
            day_number = (d - start_date).days + 1
            code = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
            label, icon = _decode_wmo(code)
            days.append({
                "date": d_str,
                "day_number": day_number,
                "temp_max_c": round(t_max[i], 1) if i < len(t_max) and t_max[i] is not None else None,
                "temp_min_c": round(t_min[i], 1) if i < len(t_min) and t_min[i] is not None else None,
                "precipitation_mm": round(precip[i], 1) if i < len(precip) and precip[i] is not None else 0.0,
                "wind_kmh": round(wind[i], 1) if i < len(wind) and wind[i] is not None else None,
                "weather_label": label,
                "weather_icon": icon,
                "is_forecast": True,
            })
        return days
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_weather_for_trip(destination: str, travel_start_date: str, num_days: int) -> dict:
    """
    Main entry point. Returns a structured weather dict:

    {
        "destination": str,
        "source": "live_forecast" | "climate_average" | "mixed",
        "unit": "°C",
        "days": [ { date, day_number, temp_max_c, temp_min_c,
                    precipitation_mm, weather_label, weather_icon,
                    is_forecast, wind_kmh? } ]
        "error": str | None
    }
    """
    try:
        start = date.fromisoformat(travel_start_date)
    except (ValueError, TypeError):
        return {"destination": destination, "days": [], "error": "Invalid travel_start_date format."}

    # Geocode
    coords = geocode_destination(destination)
    if not coords:
        return {"destination": destination, "days": [], "error": f"Could not geocode '{destination}'."}

    lat, lon = coords
    time.sleep(0.3)  # Nominatim rate-limit courtesy

    today = date.today()
    trip_end = start + timedelta(days=num_days - 1)
    forecast_cutoff = today + timedelta(days=FORECAST_HORIZON_DAYS - 1)

    forecast_days: list[dict] = []
    climate_days: list[dict] = []
    source = "live_forecast"

    if start > forecast_cutoff:
        # Entire trip is beyond forecast horizon — use climate normals
        source = "climate_average"
        climate_days = _get_climate_normals(lat, lon, start, num_days)
    elif trip_end > forecast_cutoff:
        # Trip partially in forecast window, partially beyond
        source = "mixed"
        live_days_count = (forecast_cutoff - start).days + 1
        normal_days_count = num_days - live_days_count
        normal_start = forecast_cutoff + timedelta(days=1)

        forecast_days = _get_live_forecast(lat, lon, start, live_days_count)
        climate_days = _get_climate_normals(lat, lon, normal_start, normal_days_count)
    else:
        # Entire trip within forecast horizon
        forecast_days = _get_live_forecast(lat, lon, start, num_days)

    all_days = sorted(forecast_days + climate_days, key=lambda d: d["day_number"])

    return {
        "destination": destination,
        "source": source,
        "unit": "°C",
        "days": all_days,
        "error": None if all_days else "No weather data returned from API.",
    }
