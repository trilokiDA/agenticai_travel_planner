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
    
    response = tavily.search(query=query, search_depth="advanced")
    
    context = []
    for result in response['results']:
        context.append(f"Title: {result['title']}\nContent: {result['content']}\nURL: {result['url']}\n")
    
    return "\n".join(context)
