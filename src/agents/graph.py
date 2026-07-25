import os
from typing import Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

from src.agents.state import AgentState
from src.agents.models import Itinerary, Flight, Hotel, Activity
from src.agents.prompts import get_planner_prompt
from src.tools.travel_tools import search_travel
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
    prefs = state.get("activity_preferences", [])
    
    flight_type = "ROUND TRIP" if is_round_trip else "ONE WAY"
    
    pref_str = ""
    if prefs:
        pref_str = ", ".join(prefs).lower() + " "
    
    queries = [
        f"actual {flight_type} flight prices from {origin} to {destination} in {currency} for {travel_date}",
        f"current hotel rates in {destination} per night in {currency} for {travel_date}",
        f"top {pref_str}activities within budget in {destination}"
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

    # Fetch prompt from separated prompt module
    prompt = get_planner_prompt(
        mode=mode,
        destination=destination,
        budget=budget,
        currency=currency,
        origin=origin,
        duration=duration,
        trip_type_str=trip_type_str,
        existing_itinerary_context=existing_itinerary_context,
        feedback_instruction=feedback_instruction,
        raw_data=raw_data
    )
    
    response = llm.invoke(prompt)
    content = response.content
    
    import re
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)
    
    try:
        itinerary_data = json.loads(content)
        itinerary = Itinerary(**itinerary_data)
        
        # Reconcile hotel price_per_night and total_price for mathematical consistency
        for h in itinerary.hotels:
            if duration > 0:
                expected_total = h.price_per_night * duration
                if abs(expected_total - h.total_price) > 0.01:
                    # If price_per_night is off by a large factor (5x or more),
                    # it is likely an LLM typo (like dropping a zero). Trust total_price and correct price_per_night.
                    if h.price_per_night * 5 < (h.total_price / duration):
                        h.price_per_night = h.total_price / duration
                    else:
                        # Otherwise, trust price_per_night and calculate total_price
                        h.total_price = expected_total
            else:
                h.total_price = 0.0
                h.price_per_night = 0.0

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
