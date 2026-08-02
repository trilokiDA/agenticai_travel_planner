"""
map_engine.py
-------------
Geocodes itinerary points and builds an interactive Plotly route map.
Uses Nominatim (OpenStreetMap) — completely free, no API key required.
"""

import time
import plotly.graph_objects as go
from typing import Optional

# ---------------------------------------------------------------------------
# Geocoding via Nominatim (OpenStreetMap)
# ---------------------------------------------------------------------------

def geocode_place(place_name: str, destination_hint: str = "") -> Optional[tuple[float, float]]:
    """
    Returns (lat, lon) for a place name using Nominatim REST API.
    Falls back to appending the destination as context if the first lookup fails.
    Returns None if geocoding fails.
    """
    try:
        from urllib.request import urlopen, Request
        from urllib.parse import urlencode
        import json

        def _fetch(query: str) -> Optional[tuple[float, float]]:
            params = urlencode({"q": query, "format": "json", "limit": 1})
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = Request(url, headers={"User-Agent": "AITravelPlanner/1.0"})
            with urlopen(req, timeout=5) as resp:
                results = json.loads(resp.read().decode())
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
            return None

        # First try the name as-is
        coords = _fetch(place_name)
        if coords:
            return coords

        # Try with destination context
        if destination_hint and destination_hint.lower() not in place_name.lower():
            coords = _fetch(f"{place_name}, {destination_hint}")
            if coords:
                return coords

        return None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Map Builder
# ---------------------------------------------------------------------------

CATEGORY_STYLES = {
    "Destination": {"color": "#22C55E", "symbol": "star",        "size": 18},
    "Hotel":       {"color": "#3B82F6", "symbol": "circle",      "size": 14},
    "Activity":    {"color": "#F97316", "symbol": "diamond",     "size": 12},
    "Origin":      {"color": "#A855F7", "symbol": "square",      "size": 14},
}


def build_route_map(itinerary_dict: dict, destination: str, origin: str = "") -> go.Figure:
    """
    Geocodes all itinerary points and returns a Plotly Figure with:
      - A star marker for the destination
      - Circle markers for hotels
      - Diamond markers for activities
      - A dashed route line connecting all points in visit order
    """
    points = []   # list of dicts: {lat, lon, name, category, label}

    # 1. Origin
    if origin:
        coords = geocode_place(origin)
        if coords:
            points.append({
                "lat": coords[0], "lon": coords[1],
                "name": origin, "category": "Origin",
                "label": f"🛫 Origin: {origin}"
            })
        time.sleep(0.3)  # Nominatim rate-limit courtesy

    # 2. Main destination
    dest_coords = geocode_place(destination)
    if dest_coords:
        points.append({
            "lat": dest_coords[0], "lon": dest_coords[1],
            "name": destination, "category": "Destination",
            "label": f"📍 {destination}"
        })
    time.sleep(0.3)

    # 3. Hotels
    for hotel in itinerary_dict.get("hotels", []):
        lat, lon = hotel.get("latitude"), hotel.get("longitude")
        if not (lat and lon):
            place_query = hotel.get("location") or hotel.get("name", "")
            coords = geocode_place(f"{place_query}", destination)
            if coords:
                lat, lon = coords
            time.sleep(0.3)
        if lat and lon:
            rating = hotel.get("rating")
            stars = f" ⭐ {rating}" if rating else ""
            points.append({
                "lat": lat, "lon": lon,
                "name": hotel.get("name", "Hotel"),
                "category": "Hotel",
                "label": (
                    f"🏨 {hotel.get('name', 'Hotel')}{stars}<br>"
                    f"📍 {hotel.get('location', '')}<br>"
                    f"💰 {hotel.get('price_per_night')}/night"
                )
            })

    # 4. Activities — grouped by day, deduplicated by name
    seen_activities = set()
    for activity in itinerary_dict.get("activities", []):
        act_name = activity.get("name", "")
        if act_name in seen_activities:
            continue
        seen_activities.add(act_name)

        lat, lon = activity.get("latitude"), activity.get("longitude")
        if not (lat and lon):
            # Strategy 1: use the dedicated location field (most reliable)
            act_location = activity.get("location", "")
            if act_location:
                coords = geocode_place(act_location, destination)
                if coords:
                    lat, lon = coords
                time.sleep(0.3)

            # Strategy 2: activity name + destination context
            if not (lat and lon):
                coords = geocode_place(act_name, destination)
                if coords:
                    lat, lon = coords
                time.sleep(0.3)

            # Strategy 3: activity name alone
            if not (lat and lon):
                coords = geocode_place(act_name)
                if coords:
                    lat, lon = coords
                time.sleep(0.3)

        if lat and lon:
            day_num = activity.get("day_number", "?")
            points.append({
                "lat": lat, "lon": lon,
                "name": f"Day {day_num}: {act_name}",
                "category": "Activity",
                "label": (
                    f"🎯 <b>Day {day_num}: {act_name}</b><br>"
                    f"📍 {activity.get('location', destination)}<br>"
                    f"{activity.get('description', '')}<br>"
                    f"💰 Cost: {activity.get('cost', 0)}"
                )
            })


    if not points:
        # Return an empty figure with a message
        fig = go.Figure()
        fig.update_layout(
            title="No geocodable locations found",
            paper_bgcolor="#0F172A",
            font_color="#E2E8F0"
        )
        return fig

    # ---------------------------------------------------------------------------
    # Build Plotly figure — one trace per category for clean legend
    # ---------------------------------------------------------------------------
    fig = go.Figure()

    # Route line (dashed) connecting all points in order
    if len(points) > 1:
        fig.add_trace(go.Scattermapbox(
            lat=[p["lat"] for p in points],
            lon=[p["lon"] for p in points],
            mode="lines",
            line=dict(width=3, color="#0A0A0A"),
            name="Route",
            hoverinfo="skip",
            showlegend=True,
        ))

    # One trace per category
    categories = ["Origin", "Destination", "Hotel", "Activity"]
    for cat in categories:
        cat_points = [p for p in points if p["category"] == cat]
        if not cat_points:
            continue
        style = CATEGORY_STYLES[cat]
        fig.add_trace(go.Scattermapbox(
            lat=[p["lat"] for p in cat_points],
            lon=[p["lon"] for p in cat_points],
            mode="markers+text",
            marker=go.scattermapbox.Marker(
                size=style["size"],
                color=style["color"],
                opacity=0.92,
            ),
            text=[p["name"] for p in cat_points],
            textposition="top right",
            textfont=dict(size=11, color="#F8FAFC"),
            customdata=[p["label"] for p in cat_points],
            hovertemplate="%{customdata}<extra></extra>",
            name=cat,
            showlegend=True,
        ))

    # Center map on the mean of all points
    center_lat = sum(p["lat"] for p in points) / len(points)
    center_lon = sum(p["lon"] for p in points) / len(points)

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=11,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            bgcolor="rgba(15,23,42,0.85)",
            bordercolor="#334155",
            borderwidth=1,
            font=dict(color="#E2E8F0", size=13),
            orientation="v",
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
        ),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0"),
        height=560,
    )

    return fig
