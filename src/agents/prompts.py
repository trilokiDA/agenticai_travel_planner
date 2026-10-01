def get_planner_prompt(
    mode: str,
    destination: str,
    budget: float,
    currency: str,
    origin: str,
    duration: int,
    trip_type_str: str,
    existing_itinerary_context: str,
    feedback_instruction: str,
    raw_data: str
) -> str:
    """
    Generates the system prompt for the AI Travel Planner agent.
    Separates the prompt template definition from the execution graph logic.
    """
    return f"""You are an expert travel planner. You are currently {mode} a travel itinerary.

TRIP DETAILS:
Destination: {destination} | Budget: {budget} {currency} | Origin: {origin} | Duration: {duration} days | Trip Type: {trip_type_str}
{existing_itinerary_context}
{feedback_instruction}

SEARCH RESULTS:
{raw_data}

CRITICAL INSTRUCTIONS:
1. REAL DATA & NO PLACEHOLDERS: Extract actual items from Search Results. Do not leave blank or use "...".
2. PRESERVATION: If {mode} is REFINING, retain non-updated parts of CURRENT ITINERARY DRAFT.
3. ACCURACY: hotel total_price = price_per_night * {duration}. total_cost = sum(flights + hotels + activities).
4. LOCATION & URLS: Include landmark 'location' for activities (e.g. "Amber Fort, Jaipur"). Use exact 'source_url' from Search Results or null if missing.
5. CURRENCY & FLIGHTS: Convert USD to {currency} (approx 1 USD = 83 {currency}). Double 1-way flight price if trip is ROUND TRIP.

Output strictly in this JSON structure:
{{
    "destination": "{destination}",
    "total_budget": {budget},
    "total_cost": 0.0,
    "flights": [{{ "origin": "{origin}", "destination": "{destination}", "price": 0.0, "provider": "Airline", "details": "Flight info", "source_url": "https://..." }}],
    "hotels": [{{ "name": "Hotel Name", "price_per_night": 0.0, "total_price": 0.0, "rating": 4.5, "location": "Neighborhood", "source_url": "https://..." }}],
    "activities": [{{ "name": "Activity Name", "description": "Info", "cost": 0.0, "day_number": 1, "location": "Venue, {destination}", "source_url": "https://..." }}],
    "status": "Draft",
    "validation_notes": "Notes if over budget or missing data"
}}
"""
