from graph import workflow
from state import AgentState
from models import Itinerary
from langgraph.checkpoint.memory import MemorySaver
import uuid

def run_planner_cli(destination: str, origin: str, travel_date: str, budget: float, duration: int, is_round_trip: bool = True, currency: str = "USD"):
    # Initialize the graph with a local checkpointer for the CLI
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory, interrupt_before=["human_review"])
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state: AgentState = {
        "destination": destination,
        "origin": origin,
        "travel_date": travel_date,
        "travel_start_date": "2026-06-01",
        "budget": budget,
        "currency": currency,
        "is_round_trip": is_round_trip,
        "duration_days": duration,
        "search_queries": [],
        "raw_search_results": [],
        "current_itinerary": None,
        "iteration_count": 0,
        "max_iterations": 3,
        "error": None,
        "user_feedback": None
    }
    
    print(f"Starting travel planner for {destination} from {origin} ({currency})...")
    
    # Run until the Human Review breakpoint
    app.invoke(initial_state, config)
    
    # Get the state at the breakpoint
    state = app.get_state(config)
    itinerary_data = state.values.get("current_itinerary")
    
    if itinerary_data:
        itinerary = Itinerary(**itinerary_data)
        print("\n" + "="*50)
        print(f"DRAFT ITINERARY FOR {itinerary.destination}")
        print(f"Total Budget: {budget} {currency}")
        print(f"Total Cost: {itinerary.total_cost} {currency}")
        print("="*50)
        
        # Simple approval for CLI demo
        print("\n(CLI Mode: Automatically approving draft...)")
        app.update_state(config, {"user_feedback": "APPROVE"}, as_node="human_review")
        app.invoke(None, config)
        
        # Get final state
        final_state = app.get_state(config)
        final_itinerary_data = final_state.values.get("current_itinerary")
        
        if final_itinerary_data:
            final_itinerary = Itinerary(**final_itinerary_data)
            print(f"\nFINAL STATUS: {final_itinerary.status}")
            print(f"Final Cost: {final_itinerary.total_cost} {currency}")
            print("="*50)
    else:
        print("Failed to generate an itinerary.")

if __name__ == "__main__":
    run_planner_cli(
        destination="Goa",
        origin="Delhi",
        travel_date="June 2026",
        budget=50000.0,
        duration=3,
        is_round_trip=True,
        currency="INR"
    )
