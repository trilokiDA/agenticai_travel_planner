import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

# Instantiate Tavily client globally if the API key is present
api_key = os.environ.get("TAVILY_API_KEY")
tavily = TavilyClient(api_key=api_key) if api_key else None

def search_travel(query: str) -> str:
    """
    Searches for travel information including flights, hotels, and activities using Tavily API.
    """
    if not os.environ.get("TAVILY_API_KEY"):
        return "Error: TAVILY_API_KEY not found in environment."
        
    global tavily
    if not tavily:
        tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
    
    response = tavily.search(query=query, search_depth="basic", max_results=3)
    
    context = []
    for result in response.get('results', []):
        title = result.get('title', '')
        content = result.get('content', '')[:350]  # Truncate content to 350 chars
        url = result.get('url', '')
        context.append(f"Title: {title}\nContent: {content}\nURL: {url}\n")
    
    return "\n".join(context)
