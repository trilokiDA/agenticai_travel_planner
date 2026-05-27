import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

def search_travel(query: str) -> str:
    """
    Searches for travel information including flights, hotels, and activities.
    """
    if not os.environ.get("TAVILY_API_KEY"):
        return "Error: TAVILY_API_KEY not found in environment."
    
    response = tavily.search(query=query, search_depth="advanced")
    
    context = []
    for result in response['results']:
        context.append(f"Title: {result['title']}\nContent: {result['content']}\nURL: {result['url']}\n")
    
    return "\n".join(context)
