from graph import app
from state import AgentState
import json

def run_planner(destination: str, origin: str, budget: float, duration: int, currency: str = "USD"):
    initial_state: AgentState = {
        "destination": destination,
        "origin": origin,
        "budget": budget,
        "currency": currency,
        "duration_days": duration,
        "search_queries": [],
        "raw_search_results": [],
        "current_itinerary": None,
        "iteration_count": 0,
        "max_iterations": 3,
        "error": None
    }
    
    print(f"Starting travel planner for {destination} from {origin} with budget {budget} {currency}...")
    
    final_state = app.invoke(initial_state)
    
    if final_state.get("error"):
        print(f"Error occurred: {final_state['error']}")
        return

    itinerary = final_state["current_itinerary"]
    if itinerary:
        print("\n" + "="*50)
        print(f"FINAL ITINERARY FOR {itinerary.destination}")
        print(f"Status: {itinerary.status}")
        print(f"Total Budget: {itinerary.total_budget} {currency}")
        print(f"Total Cost: {itinerary.total_cost} {currency}")
        print("="*50)
        
        print("\nFLIGHTS:")
        for f in itinerary.flights:
            print(f"- {f.provider}: {f.origin} -> {f.destination} ({currency} {f.price})")
            
        print("\nHOTELS:")
        for h in itinerary.hotels:
            print(f"- {h.name}: {currency} {h.price_per_night}/night (Total: {currency} {h.total_price})")
            
        print("\nDAILY ACTIVITIES:")
        for a in itinerary.activities:
            print(f"Day {a.day_number}: {a.name} - {a.description} ({currency} {a.cost})")
            
        if itinerary.validation_notes:
            print(f"\nNotes: {itinerary.validation_notes}")
        print("="*50)
    else:
        print("Failed to generate a valid itinerary.")

if __name__ == "__main__":
    # Example usage: Domestic travel within India in INR
    run_planner(
        destination="Goa",
        origin="Delhi",
        budget=5000.0,
        duration=3,
        currency="INR"
    )
