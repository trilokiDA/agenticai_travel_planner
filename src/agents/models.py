from typing import List, Optional
from pydantic import BaseModel, Field

class Flight(BaseModel):
    origin: str = Field(description="The departure city or airport code.")
    destination: str = Field(description="The arrival city or airport code.")
    price: float = Field(description="The price of the flight.")
    provider: str = Field(description="The airline or booking site providing the flight.")
    details: Optional[str] = Field(None, description="Any additional flight details like times or layovers.")

class Hotel(BaseModel):
    name: str = Field(description="The name of the hotel.")
    price_per_night: float = Field(description="The price per night.")
    total_price: float = Field(description="The total price for the stay.")
    rating: Optional[float] = Field(None, description="The hotel's star rating (0.0 to 5.0).")
    location: Optional[str] = Field(None, description="The general location or neighborhood of the hotel.")

class Activity(BaseModel):
    name: str = Field(description="The name of the activity or attraction.")
    description: str = Field(description="A brief description of what to do.")
    cost: float = Field(description="The cost of the activity (0.0 if free).")
    day_number: int = Field(description="The day number this activity is planned for.")

class Itinerary(BaseModel):
    destination: str = Field(description="The destination city.")
    total_budget: float = Field(description="The user's total budget for the trip.")
    total_cost: float = Field(description="The calculated total cost of the itinerary.")
    flights: List[Flight] = Field(default_factory=list, description="A list of flight options found.")
    hotels: List[Hotel] = Field(default_factory=list, description="A list of hotel options found.")
    activities: List[Activity] = Field(default_factory=list, description="The daily schedule of activities.")
    status: str = Field(description="The status of the itinerary (e.g., 'Valid', 'Over Budget', 'Incomplete').")
    validation_notes: Optional[str] = Field(None, description="Notes from the validator agent regarding issues or improvements.")
