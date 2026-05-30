from typing import TypedDict, List, Optional
from models import Itinerary

class AgentState(TypedDict):
    destination: str
    origin: str
    travel_date: str
    budget: float
    currency: str
    is_round_trip: bool
    duration_days: int
    search_queries: List[str]
    raw_search_results: List[str]
    current_itinerary: Optional[Itinerary]
    iteration_count: int
    max_iterations: int
    error: Optional[str]
