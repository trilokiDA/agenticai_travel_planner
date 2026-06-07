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
    travel_date = state["travel_date"]
    is_round_trip = state["is_round_trip"]
    
    flight_type = "ROUND TRIP" if is_round_trip else "ONE WAY"
    
    queries = [
        f"actual {flight_type} flight prices from {origin} to {destination} in {currency} for {travel_date}",
        f"current hotel rates in {destination} per night in {currency} for {travel_date}",
        f"top activities within budget in {destination}"
    ]
    
    raw_results = []
    for q in queries:
        res = search_travel(q)
        raw_results.append(res)
    
    return {
        "search_queries": queries,
        "raw_search_results": raw_results,
        "iteration_count": state.get("iteration_count", 0) + 1
    }

def planner(state: AgentState):
    """
    Parses raw data into a structured Itinerary using the LLM.
    """
    print("--- PLANNING ---")
    
    raw_search_results = state.get("raw_search_results", [])
    raw_data = "\n".join(raw_search_results) if raw_search_results else "No search data found."
        
    currency = state["currency"]
    destination = state["destination"]
    budget = state["budget"]
    origin = state["origin"]
    duration = state["duration_days"]
    trip_type_str = "ROUND TRIP" if state["is_round_trip"] else "ONE WAY"
    user_feedback = state.get("user_feedback")
    
    itinerary_dict = state.get("current_itinerary")
    
    # Context for the LLM
    mode = "REFINING" if itinerary_dict else "GENERATING"
    existing_itinerary_context = ""
    if itinerary_dict:
        existing_itinerary_context = f"\nCURRENT ITINERARY DRAFT: {json.dumps(itinerary_dict, indent=2)}"

    feedback_instruction = ""
    if user_feedback:
        feedback_instruction = f"\nUSER FEEDBACK TO INCORPORATE: '{user_feedback}'"

    prompt = f"""
    You are an expert travel planner. You are currently {mode} a travel itinerary.
    
    TRIP DETAILS:
    Destination: {destination}
    Budget: {budget} {currency}
    Origin: {origin}
    Duration: {duration} days
    Trip Type: {trip_type_str}
    
    {existing_itinerary_context}
    {feedback_instruction}
    
    SEARCH RESULTS (Use these for prices and details):
    {raw_data}
    
    CRITICAL INSTRUCTIONS:
    1. USE REAL DATA: Extract specific hotels, flights, and activities from the Search Results. 
    2. NO PLACEHOLDERS: Do not use "Not selected yet" or "..." in the final JSON. If search results contain multiple options, pick the best one within budget.
    3. PRESERVATION: If {mode} is REFINING, keep all parts of the CURRENT ITINERARY DRAFT that are not affected by the user feedback. Specifically, keep hotel ratings and flight providers stable unless changes are requested.
    4. ACCURACY: Ensure the 'total_cost' is the exact sum of flights, hotels (price_per_night * duration), and activities.
    5. REAL PRICES: If prices are higher than the budget, report the REAL price found. Let the validator handle budget issues.
    
    Provide the output in STRICT JSON format matching the structure below:
    {{
        "destination": "{destination}",
        "total_budget": {budget},
        "total_cost": 0.0,
        "flights": [{{ "origin": "{origin}", "destination": "{destination}", "price": 0.0, "provider": "Airline Name", "details": "Flight details" }}],
        "hotels": [{{ "name": "Hotel Name", "price_per_night": 0.0, "total_price": 0.0, "rating": 4.5, "location": "Neighborhood" }}],
        "activities": [
            {{ "name": "Activity Name", "description": "Description", "cost": 0.0, "day_number": 1 }}
        ],
        "status": "Draft",
        "validation_notes": "Mention here if real prices exceed budget or if data was missing."
    }}
    """
    
    response = llm.invoke(prompt)
    content = response.content
    
    import re
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)
    
    try:
        itinerary_data = json.loads(content)
        itinerary = Itinerary(**itinerary_data)
        
        # Calculate total cost programmatically to ensure accuracy
        flight_cost = sum(f.price for f in itinerary.flights)
        hotel_cost = sum(h.total_price for h in itinerary.hotels)
        activity_cost = sum(a.cost for a in itinerary.activities)
        itinerary.total_cost = flight_cost + hotel_cost + activity_cost
        
        return {"current_itinerary": itinerary.model_dump()}
    except Exception as e:
        print(f"Planner Error: {e}")
        return {"error": str(e)}

def validator(state: AgentState):
    """
    Validates the itinerary against budget and completeness.
    """
    print("--- VALIDATING ---")
    
    itinerary_dict = state.get("current_itinerary")
    if not itinerary_dict:
        return {"error": "No itinerary to validate."}
        
    itinerary = Itinerary(**itinerary_dict)
    currency = state["currency"]
    budget = state["budget"]
    
    notes = []
    is_valid = True
    
    if itinerary.total_cost > budget:
        notes.append(f"Over budget: {itinerary.total_cost} > {budget} {currency}")
        is_valid = False
    
    if not itinerary.flights:
        notes.append("Missing flight information.")
        is_valid = False
        
    if not itinerary.hotels:
        notes.append("Missing hotel information.")
        is_valid = False
        
    itinerary.status = "Valid" if is_valid else "Invalid"
    itinerary.validation_notes = ". ".join(notes)
    
    return {"current_itinerary": itinerary.model_dump()}

def human_review(state: AgentState):
    """
    A placeholder node for human intervention.
    """
    print("--- WAITING FOR HUMAN REVIEW ---")
    return {}

# Edge logic
def should_continue(state: AgentState) -> Literal["researcher", "planner", "end"]:
    feedback = state.get("user_feedback")
    if feedback and feedback.upper() != "APPROVE":
        print(f"Human requested changes: {feedback}")
        return "planner"
    
    itinerary_dict = state["current_itinerary"]
    if itinerary_dict and itinerary_dict.get("status") == "Valid":
        return "end"
    
    if state.get("iteration_count", 0) >= state.get("max_iterations", 3):
        print("Max iterations reached. Stopping.")
        return "end"
    
    return "researcher"

# Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("researcher", researcher)
workflow.add_node("planner", planner)
workflow.add_node("validator", validator)
workflow.add_node("human_review", human_review)

workflow.set_entry_point("researcher")
workflow.add_edge("researcher", "planner")
workflow.add_edge("planner", "validator")
workflow.add_edge("validator", "human_review")

workflow.add_conditional_edges(
    "human_review",
    should_continue,
    {
        "researcher": "researcher",
        "planner": "planner",
        "end": END
    }
)
