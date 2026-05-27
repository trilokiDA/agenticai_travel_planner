import os
from typing import Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from state import AgentState
from models import Itinerary, Flight, Hotel, Activity
from tools import search_travel
import json

load_dotenv()

# Initialize LLM
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.environ.get("GROQ_API_KEY")
)

# Nodes
def researcher(state: AgentState):
    """
    Generates search queries and fetches data.
    """
    print("--- RESEARCHING ---")
    destination = state["destination"]
    origin = state["origin"]
    duration = state["duration_days"]
    currency = state["currency"]
    
    # Simple query generation
    queries = [
        f"cheapest flights from {origin} to {destination} for {duration} days in {currency}",
        f"budget hotels in {destination} with prices in {currency}",
        f"top activities within budget in {destination}"
    ]
    
    raw_results = []
    for q in queries:
        raw_results.append(search_travel(q))
    
    return {
        "search_queries": queries,
        "raw_search_results": raw_results,
        "iteration_count": state["iteration_count"] + 1
    }

def planner(state: AgentState):
    """
    Parses raw data into a structured Itinerary using the LLM.
    """
    print("--- PLANNING ---")
    raw_data = "\n".join(state["raw_search_results"])
    currency = state["currency"]
    
    prompt = f"""
    Based on the following search results, create a structured travel itinerary for {state['destination']} with a budget of {state['budget']} {currency}.
    The user is traveling from {state['origin']} for {state['duration_days']} days.
    
    Search Results:
    {raw_data}
    
    Instructions:
    1. Extract at least one flight option and one hotel option with prices in {currency}.
    2. Plan 2-3 activities per day.
    3. Calculate the total cost in {currency}.
    4. Provide the output in STRICT JSON format matching the Itinerary model.
    
    JSON Structure to follow:
    {{
        "destination": "...",
        "total_budget": {state['budget']},
        "total_cost": 0.0,
        "flights": [{{ "origin": "...", "destination": "...", "price": 0.0, "provider": "..." }}],
        "hotels": [{{ "name": "...", "price_per_night": 0.0, "total_price": 0.0, "rating": 4.5 }}],
        "activities": [{{ "name": "...", "description": "...", "cost": 0.0, "day_number": 1 }}],
        "status": "Incomplete",
        "validation_notes": ""
    }}
    """
    
    response = llm.invoke(prompt)
    
    # Try to extract JSON from the response
    content = response.content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    
    try:
        itinerary_data = json.loads(content)
        itinerary = Itinerary(**itinerary_data)
        return {"current_itinerary": itinerary}
    except Exception as e:
        print(f"Error parsing itinerary: {e}")
        return {"error": str(e)}

def validator(state: AgentState):
    """
    Validates the itinerary against budget and completeness.
    """
    print("--- VALIDATING ---")
    itinerary = state["current_itinerary"]
    currency = state["currency"]
    
    if not itinerary:
        return {"error": "No itinerary to validate."}
    
    notes = []
    is_valid = True
    
    if itinerary.total_cost > state["budget"]:
        notes.append(f"Over budget: {itinerary.total_cost} > {state['budget']} {currency}")
        is_valid = False
    
    if not itinerary.flights:
        notes.append("Missing flight information.")
        is_valid = False
        
    if not itinerary.hotels:
        notes.append("Missing hotel information.")
        is_valid = False
        
    itinerary.status = "Valid" if is_valid else "Invalid"
    itinerary.validation_notes = ". ".join(notes)
    
    return {"current_itinerary": itinerary}

# Edge logic
def should_continue(state: AgentState) -> Literal["researcher", "end"]:
    itinerary = state["current_itinerary"]
    if itinerary and itinerary.status == "Valid":
        return "end"
    if state["iteration_count"] >= state["max_iterations"]:
        print("Max iterations reached. Stopping.")
        return "end"
    return "researcher"

# Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("researcher", researcher)
workflow.add_node("planner", planner)
workflow.add_node("validator", validator)

workflow.set_entry_point("researcher")
workflow.add_edge("researcher", "planner")
workflow.add_edge("planner", "validator")

workflow.add_conditional_edges(
    "validator",
    should_continue,
    {
        "researcher": "researcher",
        "end": END
    }
)

app = workflow.compile()
