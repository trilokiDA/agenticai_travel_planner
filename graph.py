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
    print(f"--- RESEARCHING ({'ROUND TRIP' if state['is_round_trip'] else 'ONE WAY'}) ---")
    destination = state["destination"]
    origin = state["origin"]
    duration = state["duration_days"]
    currency = state["currency"]
    travel_date = state["travel_date"]
    is_round_trip = state["is_round_trip"]
    
    flight_type = "ROUND TRIP" if is_round_trip else "ONE WAY"
    
    # Improved query generation for realistic prices
    queries = [
        f"actual {flight_type} flight prices from {origin} to {destination} in {currency} for {travel_date}",
        f"current hotel rates in {destination} per night in {currency} for {travel_date}",
        f"top activities within budget in {destination}"
    ]
    
    raw_results = []
    for q in queries:
        res = search_travel(q)
        print(f"DEBUG: Query: {q} | Result length: {len(res)}")
        raw_results.append(res)
    
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
    trip_type_str = "ROUND TRIP" if state["is_round_trip"] else "ONE WAY"
    
    prompt = f"""
    Based on the following search results, create a structured travel itinerary for {state['destination']} with a budget of {state['budget']} {currency}.
    The user is traveling from {state['origin']} for {state['duration_days']} days.
    THIS IS A {trip_type_str} JOURNEY.
    
    Search Results:
    {raw_data}
    
    CRITICAL INSTRUCTIONS:
    1. USE REAL PRICES found in the search results. DO NOT hallucinate or make up low prices to fit the budget.
    2. If a flight or hotel is not found in the search results, or if the prices are clearly much higher than the budget, report the REAL price anyway and let the validator handle it.
    3. If you cannot find any pricing data, set the price to 0.0 and mention this in the 'validation_notes'.
    4. Provide the output in STRICT JSON format matching the Itinerary model.
    5. The 'total_cost' should be the sum of all components.
    6. Plan at least 2-3 varied activities per day to provide a full experience.
    7. IMPORTANT: For {trip_type_str} flights, ensure the price reflects the TOTAL cost for the entire journey (both ways if Round Trip).
       - If you find a round-trip price, provide it as a single flight entry with origin and destination.
       - If you find only one-way prices for a Round Trip request, you MUST either provide two flight entries (Outbound and Inbound) OR provide one entry with the price DOUBLED.
       - Clearly mention in 'validation_notes' how the flight price was calculated (e.g., "Round trip price found" or "One-way price doubled for round trip").
    
    JSON Structure to follow:
    {{
        "destination": "...",
        "total_budget": {state['budget']},
        "total_cost": 0.0,
        "flights": [{{ "origin": "...", "destination": "...", "price": 0.0, "provider": "...", "details": "Round Trip" }}],
        "hotels": [{{ "name": "...", "price_per_night": 0.0, "total_price": 0.0, "rating": 4.5 }}],
        "activities": [
            {{ "name": "Activity 1", "description": "...", "cost": 0.0, "day_number": 1 }},
            {{ "name": "Activity 2", "description": "...", "cost": 0.0, "day_number": 1 }}
        ],
        "status": "Incomplete",
        "validation_notes": "Mention here if real prices exceed budget or if data was missing."
    }}
    """
    
    response = llm.invoke(prompt)
    content = response.content
    
    # Try to extract JSON from the response
    import re
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)
    
    try:
        itinerary_data = json.loads(content)
        itinerary = Itinerary(**itinerary_data)
        
        # Programmatically calculate total cost to ensure accuracy
        flight_cost = sum(f.price for f in itinerary.flights)
        hotel_cost = sum(h.total_price for h in itinerary.hotels)
        activity_cost = sum(a.cost for a in itinerary.activities)
        itinerary.total_cost = flight_cost + hotel_cost + activity_cost
        
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
