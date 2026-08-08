from typing import TypedDict, List, Optional, Annotated, Any
import operator

def merge_if_not_none(old: Any, new: Any) -> Any:
    """
    Ensures state keys are preserved unless explicitly updated with a non-None value.
    """
    if new is not None:
        return new
    return old

class AgentState(TypedDict):
    # Core trip details - Now sticky to prevent vanishing
    destination: Annotated[str, merge_if_not_none]
    origin: Annotated[str, merge_if_not_none]
    travel_date: Annotated[str, merge_if_not_none]
    travel_start_date: Annotated[Optional[str], merge_if_not_none]
    budget: Annotated[float, merge_if_not_none]
    currency: Annotated[str, merge_if_not_none]
    is_round_trip: Annotated[bool, merge_if_not_none]
    duration_days: Annotated[int, merge_if_not_none]
    activity_preferences: Annotated[List[str], merge_if_not_none]
    
    # Lists that accumulate
    search_queries: Annotated[List[str], operator.add]
    raw_search_results: Annotated[List[str], operator.add]
    
    # Plan results - Also sticky
    current_itinerary: Annotated[Optional[dict], merge_if_not_none]
    iteration_count: Annotated[int, merge_if_not_none]
    max_iterations: Annotated[int, merge_if_not_none]
    error: Annotated[Optional[str], merge_if_not_none]
    user_feedback: Annotated[Optional[str], merge_if_not_none]

    # Weather forecast/climate data for the destination & travel dates
    weather_data: Annotated[Optional[dict], merge_if_not_none]
