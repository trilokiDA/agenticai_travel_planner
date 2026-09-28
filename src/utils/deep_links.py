import urllib.parse
from typing import Optional

def generate_flight_link(origin: str, destination: str, travel_date: Optional[str]) -> str:
    """Generate a Google Flights search link."""
    query = f"Flights from {origin} to {destination}"
    if travel_date:
        query += f" on {travel_date}"
    encoded_query = urllib.parse.quote(query)
    return f"https://www.google.com/search?tbm=flw&q={encoded_query}"

def generate_hotel_link(hotel_name: str, destination: str) -> str:
    """Generate a Booking.com search link."""
    query = f"{hotel_name} {destination}"
    encoded_query = urllib.parse.quote(query)
    return f"https://www.booking.com/searchresults.html?ss={encoded_query}"

def generate_activity_link(activity_name: str, destination: str) -> str:
    """Generate a TripAdvisor search link."""
    query = f"{activity_name} {destination}"
    encoded_query = urllib.parse.quote(query)
    return f"https://www.tripadvisor.com/Search?q={encoded_query}"
