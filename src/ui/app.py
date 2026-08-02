import sys
import os
import plotly.graph_objects as go

# Ensure the project root (v1/) is in sys.path so `src.*` imports work
# when Streamlit runs this file directly from any working directory.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import uuid
import json
import pandas as pd
from src.agents.state import AgentState
from src.agents.models import Itinerary, Flight, Hotel, Activity
from dotenv import load_dotenv
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional
from langgraph.checkpoint.memory import MemorySaver

def get_itinerary_history(planner_app, config):
    try:
        history = list(planner_app.get_state_history(config))
    except Exception:
        return []
    
    unique_drafts = []
    seen_itineraries = set()
    for checkpoint in history:
        itinerary = checkpoint.values.get("current_itinerary")
        if itinerary:
            # Create a signature to deduplicate identical itineraries
            sig = (
                itinerary.get("destination"),
                itinerary.get("total_cost"),
                len(itinerary.get("flights", [])),
                len(itinerary.get("hotels", [])),
                len(itinerary.get("activities", []))
            )
            if sig not in seen_itineraries:
                seen_itineraries.add(sig)
                unique_drafts.append(checkpoint)
    
    # Chronological numbering (oldest to newest)
    unique_drafts.reverse()
    numbered_drafts = []
    for idx, checkpoint in enumerate(unique_drafts):
        numbered_drafts.append({
            "version": idx + 1,
            "checkpoint": checkpoint,
            "itinerary": checkpoint.values.get("current_itinerary")
        })
    
    # Return newest first for display
    return list(reversed(numbered_drafts))

load_dotenv()

today = datetime.now().date()

st.set_page_config(page_title="AI Travel Planner", page_icon="✈️", layout="wide")

# Custom CSS for modern, premium styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    /* Global Font & Smooth Scaling */
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Clean Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #1E293B;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p, 
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
    [data-testid="stSidebar"] label {
        color: #E2E8F0 !important;
        font-weight: 500;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }
    
    /* Primary buttons styling */
    div.stButton > button {
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 20px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2), 0 2px 4px -1px rgba(37, 99, 235, 0.1) !important;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #60A5FA 0%, #2563EB 100%) !important;
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.3), 0 4px 6px -2px rgba(37, 99, 235, 0.15) !important;
        transform: translateY(-1px) !important;
    }
    
    /* Secondary/Reset buttons styling */
    div.stButton > button[kind="secondary"] {
        background: #1E293B !important;
        border: 1px solid #334155 !important;
        color: #F8FAFC !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background: #334155 !important;
        color: white !important;
    }
    
    /* Clean metrics cards with subtle shadow and border */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 15px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #1E3A8A !important;
        font-weight: 700;
    }
    
    /* Modern Tabs layout */
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 12px 20px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("✈️ AI Travel Planner")
st.markdown("Plan your next adventure with Human-in-the-loop AI agents!")

# PERSISTENCE FIX: Cache the entire app AND its checkpointer to survive Streamlit reruns
@st.cache_resource
def get_planner_app():
    from src.agents.graph import workflow
    checkpointer = MemorySaver()
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"]
    )

planner_app = get_planner_app()

# Initialize session state for the thread
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "current_state" not in st.session_state:
    st.session_state.current_state = None

if "loaded_values" not in st.session_state:
    st.session_state.loaded_values = None

# Apply loaded values to widget keys before widgets are instantiated on the next run
if st.session_state.loaded_values is not None:
    st.session_state.dest = st.session_state.loaded_values["destination"]
    st.session_state.orig = st.session_state.loaded_values["origin"]
    st.session_state.budget_val = st.session_state.loaded_values["budget"]
    st.session_state.currency_val = st.session_state.loaded_values["currency"]
    st.session_state.activity_prefs_val = st.session_state.loaded_values.get("activity_preferences", [])
    
    # Restore Trip Type
    is_round_trip = st.session_state.loaded_values.get("is_round_trip", True)
    st.session_state.trip_type_radio = "Round Trip" if is_round_trip else "One Way"
    
    # Restore Start Date and End Date / Duration
    start_date_str = st.session_state.loaded_values.get("travel_start_date")
    duration_days = st.session_state.loaded_values.get("duration_days", 3)
    
    if start_date_str:
        try:
            start_date_parsed = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            st.session_state.start_date_val = start_date_parsed
            
            if is_round_trip:
                end_date_parsed = start_date_parsed + timedelta(days=duration_days - 1)
                st.session_state.end_date_val = end_date_parsed
            else:
                st.session_state.duration_val = int(duration_days)
        except Exception:
            pass
    # Clear the temporary storage
    st.session_state.loaded_values = None

# Sidebar for inputs
with st.sidebar:
    st.header("Trip Details")
    destination = st.text_input("Destination", placeholder="Paris, Goa", key="dest")
    origin = st.text_input("Origin", placeholder="London, Delhi", key="orig")
    
    # Dynamically determine min_value to allow loaded dates in the past without Streamlit crashes
    loaded_start_date = st.session_state.get("start_date_val")
    min_val_start = today
    if loaded_start_date and isinstance(loaded_start_date, date) and loaded_start_date < today:
        min_val_start = loaded_start_date

    trip_type = st.radio("Trip Type", ["Round Trip", "One Way"], index=0, key="trip_type_radio")
    
    if trip_type == "Round Trip":
        col1, col2 = st.columns(2)
        start_date = col1.date_input(
            "Start Date", 
            value=st.session_state.get("start_date_val", None), 
            min_value=min_val_start,
            key="start_date_val"
        )
        
        # Determine min_value for end_date dynamically
        loaded_end_date = st.session_state.get("end_date_val")
        min_val_end = start_date if start_date else today
        if loaded_end_date and isinstance(loaded_end_date, date):
            if start_date and loaded_end_date < start_date:
                min_val_end = loaded_end_date
            elif not start_date and loaded_end_date < today:
                min_val_end = loaded_end_date
                
        end_date = col2.date_input(
            "End Date", 
            value=st.session_state.get("end_date_val", None), 
            min_value=min_val_end,
            key="end_date_val"
        )
        duration = (end_date - start_date).days + 1 if start_date and end_date else 0
        is_round_trip = True
    else:
        start_date = st.date_input(
            "Start Date", 
            value=st.session_state.get("start_date_val", None), 
            min_value=min_val_start,
            key="start_date_val"
        )
        duration = st.slider(
            "Duration (Days)", 
            min_value=1, 
            max_value=14, 
            value=st.session_state.get("duration_val", 3),
            key="duration_val"
        )
        is_round_trip = False
        
    budget = st.number_input("Budget", min_value=1.0, value=50000.0, key="budget_val")
    currency = st.selectbox("Currency", options=["INR", "USD"], index=0, key="currency_val")
    
    # Activity Customization Preferences
    activity_prefs = st.multiselect(
        "Activity Preferences", 
        options=["Adventure", "Cultural", "Relaxation", "Food & Dining", "Nature & Outdoors", "Shopping", "Nightlife"],
        default=st.session_state.get("activity_prefs_val", []),
        key="activity_prefs_val"
    )
    
    if st.button("Start New Planning"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.current_state = None
        
        if not destination or not origin or not start_date or duration <= 0:
            st.error("Please provide all trip details.")
        else:
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            initial_state = {
                "destination": destination,
                "origin": origin,
                "travel_date": start_date.strftime("%B %Y"),
                "travel_start_date": start_date.strftime("%Y-%m-%d"),
                "budget": budget,
                "currency": currency,
                "is_round_trip": is_round_trip,
                "duration_days": duration,
                "activity_preferences": activity_prefs,
                "search_queries": [],
                "raw_search_results": [],
                "current_itinerary": None,
                "iteration_count": 0,
                "max_iterations": 3,
                "error": None,
                "user_feedback": None
            }
            with st.spinner("Researching and planning..."):
                planner_app.invoke(initial_state, config)
                st.session_state.current_state = planner_app.get_state(config)
                
    st.markdown("---")
    st.subheader("💾 Save & Load Plan")
    
    # 1. Save / Download current itinerary
    has_active_itinerary = (
        st.session_state.current_state is not None 
        and st.session_state.current_state.values.get("current_itinerary") is not None
    )
    
    if has_active_itinerary:
        state_vals = st.session_state.current_state.values
        itinerary_data = state_vals.get("current_itinerary")
        dest_clean = itinerary_data.get("destination", "trip").lower().replace(" ", "_")
        
        # Prepare state values to save
        save_data = {
            "destination": state_vals.get("destination"),
            "origin": state_vals.get("origin"),
            "travel_date": state_vals.get("travel_date"),
            "travel_start_date": state_vals.get("travel_start_date"),
            "budget": state_vals.get("budget"),
            "currency": state_vals.get("currency"),
            "is_round_trip": state_vals.get("is_round_trip"),
            "duration_days": state_vals.get("duration_days"),
            "activity_preferences": state_vals.get("activity_preferences", []),
            "search_queries": state_vals.get("search_queries", []),
            "raw_search_results": state_vals.get("raw_search_results", []),
            "current_itinerary": state_vals.get("current_itinerary"),
            "iteration_count": state_vals.get("iteration_count", 0),
            "max_iterations": state_vals.get("max_iterations", 3),
            "error": state_vals.get("error"),
            "user_feedback": state_vals.get("user_feedback")
        }
        json_str = json.dumps(save_data, indent=2, default=str)
        
        st.download_button(
            label="📥 Export Plan (JSON)",
            data=json_str,
            file_name=f"itinerary_{dest_clean}.json",
            mime="application/json",
            use_container_width=True
        )
    else:
        st.info("Start planning to enable download.")
        
    st.markdown("---")
    
    # 2. Load itinerary from JSON file
    uploaded_file = st.file_uploader("Import Saved Plan (.json)", type=["json"])
    if uploaded_file is not None:
        try:
            loaded_vals = json.loads(uploaded_file.read().decode("utf-8"))
            
            # Validation
            required_keys = ["destination", "origin", "current_itinerary"]
            if not all(k in loaded_vals for k in required_keys):
                st.error("Invalid itinerary file format.")
            else:
                if st.button("🚀 Load Itinerary", type="primary", use_container_width=True):
                    # Sanitize loaded values to fit AgentState
                    sanitized_vals = {
                        "destination": loaded_vals.get("destination"),
                        "origin": loaded_vals.get("origin"),
                        "travel_date": loaded_vals.get("travel_date"),
                        "travel_start_date": loaded_vals.get("travel_start_date"),
                        "budget": loaded_vals.get("budget", 50000.0),
                        "currency": loaded_vals.get("currency", "USD"),
                        "is_round_trip": loaded_vals.get("is_round_trip", True),
                        "duration_days": loaded_vals.get("duration_days", 1),
                        "activity_preferences": loaded_vals.get("activity_preferences", []),
                        "search_queries": loaded_vals.get("search_queries", []),
                        "raw_search_results": loaded_vals.get("raw_search_results", []),
                        "current_itinerary": loaded_vals.get("current_itinerary"),
                        "iteration_count": loaded_vals.get("iteration_count", 0),
                        "max_iterations": loaded_vals.get("max_iterations", 3),
                        "error": loaded_vals.get("error"),
                        "user_feedback": loaded_vals.get("user_feedback")
                    }
                    
                    # Generate a new unique thread ID to avoid state collision
                    st.session_state.thread_id = str(uuid.uuid4())
                    config = {"configurable": {"thread_id": st.session_state.thread_id}}
                    
                    # Store sanitized values in temporary session state to synchronize widgets on rerun
                    st.session_state.loaded_values = sanitized_vals
                    
                    # Pre-populate checkpoint memory with the loaded state values
                    planner_app.update_state(config, sanitized_vals, as_node="human_review")
                    
                    # Update session state with the restored state
                    st.session_state.current_state = planner_app.get_state(config)
                    st.success("Plan loaded successfully!")
                    st.rerun()
        except Exception as e:
            st.error(f"Error loading file: {e}")

# Helper to display itinerary
def display_itinerary_ui(itinerary: Itinerary, budget: float, currency: str, duration: int, travel_start_date: Optional[str], origin: str, is_round_trip: bool, activity_preferences: Optional[list] = None):
    st.success(f"### 🎊 Itinerary for {itinerary.destination}")
    
    if activity_preferences:
        badge_html = "".join([f'<span style="background-color: #EFF6FF; color: #1E40AF; border: 1px solid #BFDBFE; border-radius: 9999px; padding: 4px 12px; margin-right: 8px; font-size: 0.85rem; font-weight: 500; display: inline-block; margin-bottom: 10px;">🏷️ {pref}</span>' for pref in activity_preferences])
        st.markdown(f'<div style="margin-top: -10px; margin-bottom: 15px;">{badge_html}</div>', unsafe_allow_html=True)
        
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Budget", f"{budget} {currency}")
    col2.metric("Total Cost", f"{itinerary.total_cost} {currency}")
    col3.metric("Status", itinerary.status)
    
    if itinerary.validation_notes:
        st.warning(f"**Validation Notes:** {itinerary.validation_notes}")
        
    st.write("---")
    
    # --- Budget Breakdown & Analytics Section ---
    st.subheader("📊 Budget Breakdown & Analytics")
    
    # Calculate costs per category
    flight_cost = sum(f.price for f in itinerary.flights)
    hotel_cost = sum(h.total_price for h in itinerary.hotels)
    activity_cost = sum(a.cost for a in itinerary.activities)
    total_cost = flight_cost + hotel_cost + activity_cost
    
    # Calculate budget utilization
    pct_used = min(total_cost / budget, 2.0) if budget > 0 else 0.0
    pct_label = f"{total_cost / budget * 100:.1f}%" if budget > 0 else "0%"
    
    # Set progress bar color and messages based on utilization
    if pct_used <= 0.8:
        progress_color = "#10B981"  # Emerald Green
        status_text = "Good! Well within budget."
    elif pct_used <= 1.0:
        progress_color = "#F59E0B"  # Amber Orange
        status_text = "Caution! Nearing budget limit."
    else:
        progress_color = "#EF4444"  # Red
        status_text = "Alert! Over budget."
        
    # HTML custom progress bar with rich styling
    st.markdown(f"""
        <div style="margin-bottom: 20px; background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 15px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-weight: 600; font-size: 0.95rem; color: #1E293B;">Budget Utilization: <strong>{pct_label}</strong></span>
                <span style="font-size: 0.9rem; color: {progress_color}; font-weight: bold;">{status_text}</span>
            </div>
            <div style="background-color: #E2E8F0; border-radius: 9999px; height: 14px; width: 100%; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);">
                <div style="background-color: {progress_color}; height: 100%; width: {pct_used * 100}%; border-radius: 9999px; transition: width 0.5s ease-in-out;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    chart_col, data_col = st.columns([2, 1])
    
    with chart_col:
        # Create categories data for Altair chart in Streamlit
        chart_data = pd.DataFrame({
            "Category": ["Flights", "Hotels", "Activities"],
            "Cost": [flight_cost, hotel_cost, activity_cost]
        })
        
        # Display Streamlit native bar chart
        st.bar_chart(
            chart_data, 
            x="Category", 
            y="Cost", 
            color="Category",
            x_label="Expense Category",
            y_label=f"Cost ({currency})",
            use_container_width=True
        )
        
    with data_col:
        st.markdown("<p style='font-size: 1rem; font-weight: bold; margin-bottom: 10px; color: #0F172A;'>Expense Summary</p>", unsafe_allow_html=True)
        
        breakdown_html = f"""
        <table style="width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 0.95rem; margin-bottom: 15px;">
            <tr style="border-bottom: 1px solid #E2E8F0; height: 38px;">
                <td style="font-weight: 500; color: #475569;">✈️ Flights</td>
                <td style="text-align: right; font-weight: 600; color: #1E293B;">{flight_cost:,.2f} {currency}</td>
            </tr>
            <tr style="border-bottom: 1px solid #E2E8F0; height: 38px;">
                <td style="font-weight: 500; color: #475569;">🏨 Hotels</td>
                <td style="text-align: right; font-weight: 600; color: #1E293B;">{hotel_cost:,.2f} {currency}</td>
            </tr>
            <tr style="border-bottom: 1px solid #E2E8F0; height: 38px;">
                <td style="font-weight: 500; color: #475569;">📍 Activities</td>
                <td style="text-align: right; font-weight: 600; color: #1E293B;">{activity_cost:,.2f} {currency}</td>
            </tr>
            <tr style="height: 45px; border-top: 2px solid #CBD5E1;">
                <td style="font-weight: bold; color: #0F172A;">Total Spend</td>
                <td style="text-align: right; font-weight: bold; font-size: 1.1rem; color: {progress_color if pct_used > 1.0 else '#0F172A'};">{total_cost:,.2f} {currency}</td>
            </tr>
        </table>
        """
        st.markdown(breakdown_html, unsafe_allow_html=True)
        
        remaining = budget - total_cost
        if remaining >= 0:
            st.success(f"💰 Remaining: **{remaining:,.2f} {currency}**")
        else:
            st.error(f"⚠️ Over Budget by: **{abs(remaining):,.2f} {currency}**")
            
    st.write("---")
    st.markdown("##### 📤 Export Options")
    exp_col1, exp_col2 = st.columns(2)
    
    from src.utils.export_engine import generate_ics, generate_pdf
    
    itinerary_dict = itinerary.model_dump()
    itinerary_dict["duration_days"] = duration
    itinerary_dict["currency"] = currency
    itinerary_dict["origin"] = origin
    itinerary_dict["is_round_trip"] = is_round_trip
    itinerary_dict["activity_preferences"] = itinerary_dict.get("activity_preferences") or state_values.get("activity_preferences", [])
    
    with exp_col1:
        try:
            pdf_data = generate_pdf(itinerary_dict, budget, currency, travel_start_date)
            st.download_button(
                label="📥 Download PDF Itinerary",
                data=pdf_data,
                file_name=f"itinerary_{itinerary.destination.lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Failed to generate PDF: {e}")
            
    with exp_col2:
        try:
            ics_data = generate_ics(itinerary_dict, travel_start_date)
            st.download_button(
                label="📅 Export to Calendar (ICS)",
                data=ics_data,
                file_name=f"itinerary_{itinerary.destination.lower().replace(' ', '_')}.ics",
                mime="text/calendar",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Failed to generate ICS Calendar: {e}")
            
    st.write("---")
    
    # We use local references to tabs since st.tabs returns them in order
    tabs = st.tabs(["✈️ Flights", "🏨 Hotels", "📅 Daily Schedule", "🗺️ Route Map"])
    tab1, tab2, tab3, tab4 = tabs[0], tabs[1], tabs[2], tabs[3]
    
    with tab1:
        for f in itinerary.flights:
            st.write(f"**{f.provider}**: {f.origin} → {f.destination} (**{currency} {f.price}**)")
            if f.details:
                st.caption(f"Details: {f.details}")
    
    with tab2:
        for h in itinerary.hotels:
            st.write(f"**{h.name}**: {currency} {h.price_per_night}/night (Total: **{currency} {h.total_price}**)")
            if h.rating:
                st.write(f"⭐ Rating: {h.rating}")
            if h.location:
                st.caption(f"Location: {h.location}")
    
    with tab3:
        for day in range(1, duration + 1):
            day_activities = [a for a in itinerary.activities if a.day_number == day]
            with st.expander(f"📅 Day {day}", expanded=(day == 1)):
                if day_activities:
                    for a in day_activities:
                        st.write(f"📍 **{a.name}** - {a.description} (**{currency} {a.cost}**)")
                else:
                    st.caption("No activities scheduled for this day. Relax or explore the local area!")

    with tab4:
        from src.utils.map_engine import build_route_map

        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%);
                        border: 1px solid #334155; border-radius: 10px;
                        padding: 12px 18px; margin-bottom: 16px;">
                <span style="color:#94A3B8; font-size:0.9rem;">
                    🌐 Map data powered by <strong style="color:#E2E8F0;">OpenStreetMap / Nominatim</strong>
                    — 100% free, no API key required.
                    Geocoding may take a few seconds.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Legend key
        legend_html = """
        <div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:14px;">
            <span style="color:#22C55E;">★ Destination</span>
            <span style="color:#A855F7;">■ Origin</span>
            <span style="color:#3B82F6;">● Hotel</span>
            <span style="color:#F97316;">◆ Activity</span>
            <span style="color:#0A0A0A; font-weight:800;">— Route</span>
        </div>
        """
        st.markdown(legend_html, unsafe_allow_html=True)

        with st.spinner("📡 Geocoding locations via OpenStreetMap..."):
            itinerary_dict_for_map = itinerary.model_dump()
            fig = build_route_map(
                itinerary_dict=itinerary_dict_for_map,
                destination=itinerary.destination,
                origin=origin,
            )

        st.plotly_chart(fig, use_container_width=True, config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"route_map_{itinerary.destination.lower().replace(' ', '_')}",
                "height": 600,
                "width": 1000,
                "scale": 2
            }
        })

        # Stats below the map
        num_hotels = len(itinerary.hotels)
        num_activities = len(set(a.name for a in itinerary.activities))
        st.markdown(
            f"""
            <div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:10px;">
                <div style="background:#1E293B; border:1px solid #334155; border-radius:8px;
                            padding:10px 18px; flex:1; min-width:150px; text-align:center;">
                    <div style="font-size:1.5rem;">🏨</div>
                    <div style="color:#94A3B8; font-size:0.8rem;">Hotels Mapped</div>
                    <div style="color:#E2E8F0; font-weight:700; font-size:1.2rem;">{num_hotels}</div>
                </div>
                <div style="background:#1E293B; border:1px solid #334155; border-radius:8px;
                            padding:10px 18px; flex:1; min-width:150px; text-align:center;">
                    <div style="font-size:1.5rem;">🎯</div>
                    <div style="color:#94A3B8; font-size:0.8rem;">Activities Mapped</div>
                    <div style="color:#E2E8F0; font-weight:700; font-size:1.2rem;">{num_activities}</div>
                </div>
                <div style="background:#1E293B; border:1px solid #334155; border-radius:8px;
                            padding:10px 18px; flex:1; min-width:150px; text-align:center;">
                    <div style="font-size:1.5rem;">🌍</div>
                    <div style="color:#94A3B8; font-size:0.8rem;">Destination</div>
                    <div style="color:#E2E8F0; font-weight:700; font-size:1.2rem;">{itinerary.destination}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# Display Logic
if st.session_state.current_state:
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    state_values = st.session_state.current_state.values
    itinerary_data = state_values.get("current_itinerary")
    
    if itinerary_data:
        # Restore the rich UI
        itinerary = Itinerary(**itinerary_data)
        display_itinerary_ui(
            itinerary, 
            state_values.get('budget', 0.0), 
            state_values.get('currency', 'USD'), 
            state_values.get('duration_days', 1),
            state_values.get('travel_start_date'),
            state_values.get('origin', 'Origin'),
            state_values.get('is_round_trip', True),
            state_values.get('activity_preferences', [])
        )
        
        # --- Version History & Comparison Section ---
        history_drafts = get_itinerary_history(planner_app, config)
        if len(history_drafts) > 1:
            st.divider()
            st.subheader("🕒 Draft History & Version Control")
            st.markdown("Compare previous versions of the travel plan side-by-side and restore any draft if you prefer it.")
            
            # Map checkpoint versions to labels
            current_checkpoint_id = st.session_state.current_state.config["configurable"].get("checkpoint_id")
            current_idx = next(
                (d["version"] for d in history_drafts 
                 if d["checkpoint"].config["configurable"].get("checkpoint_id") == current_checkpoint_id), 
                len(history_drafts)
            )
            
            options_map = {}
            for d in history_drafts:
                v_num = d["version"]
                cost = d["itinerary"].get("total_cost")
                curr = state_values.get("currency", "USD")
                is_active = " (Active)" if v_num == current_idx else ""
                label = f"Draft {v_num} - {cost} {curr}{is_active}"
                options_map[label] = d
                
            selected_label = st.selectbox("Select a draft to compare with the active plan", options=list(options_map.keys()), index=0)
            
            if selected_label:
                selected_draft = options_map[selected_label]
                sel_itinerary = Itinerary(**selected_draft["itinerary"])
                sel_version = selected_draft["version"]
                
                # Check if it's the active one
                is_active_selected = (sel_version == current_idx)
                
                # Layout comparison columns
                comp_col1, comp_col2 = st.columns(2)
                
                with comp_col1:
                    st.info(f"### 🟢 Active Draft (Draft {current_idx})")
                    st.metric("Total Cost", f"{itinerary.total_cost} {state_values.get('currency', 'USD')}")
                    
                    if itinerary.flights:
                        st.markdown("**Flights:**")
                        for f in itinerary.flights:
                            st.write(f"- ✈️ {f.provider}: {f.origin} → {f.destination} ({f.price} {state_values.get('currency', 'USD')})")
                    
                    if itinerary.hotels:
                        st.markdown("**Hotels:**")
                        for h in itinerary.hotels:
                            st.write(f"- 🏨 {h.name} ({h.price_per_night}/night, Total: {h.total_price})")
                            
                    with st.expander("View Daily Activities"):
                        for day in range(1, state_values.get('duration_days', 1) + 1):
                            day_activities = [a for a in itinerary.activities if a.day_number == day]
                            if day_activities:
                                st.markdown(f"**Day {day}**")
                                for a in day_activities:
                                    st.write(f"- 📍 {a.name} ({a.cost})")
                                    
                with comp_col2:
                    st.warning(f"### 🟡 Selected Draft (Draft {sel_version})")
                    st.metric("Total Cost", f"{sel_itinerary.total_cost} {state_values.get('currency', 'USD')}")
                    
                    if sel_itinerary.flights:
                        st.markdown("**Flights:**")
                        for f in sel_itinerary.flights:
                            st.write(f"- ✈️ {f.provider}: {f.origin} → {f.destination} ({f.price} {state_values.get('currency', 'USD')})")
                    
                    if sel_itinerary.hotels:
                        st.markdown("**Hotels:**")
                        for h in sel_itinerary.hotels:
                            st.write(f"- 🏨 {h.name} ({h.price_per_night}/night, Total: {h.total_price})")
                            
                    with st.expander(f"View Draft {sel_version} Activities"):
                        for day in range(1, state_values.get('duration_days', 1) + 1):
                            day_activities = [a for a in sel_itinerary.activities if a.day_number == day]
                            if day_activities:
                                st.markdown(f"**Day {day}**")
                                for a in day_activities:
                                    st.write(f"- 📍 {a.name} ({a.cost})")
                    
                    if not is_active_selected:
                        if st.button(f"Restore Draft {sel_version}", type="primary"):
                            with st.spinner(f"Restoring Draft {sel_version}..."):
                                # Extract full checkpoint values from selected draft
                                selected_values = selected_draft["checkpoint"].values.copy()
                                # Set user_feedback to empty string to prevent reducer issues and avoid triggering should_continue
                                selected_values["user_feedback"] = ""
                                planner_app.update_state(config, selected_values, as_node="human_review")
                                st.session_state.current_state = planner_app.get_state(config)
                                st.rerun()
            
    if st.session_state.current_state.next:
        st.divider()
        st.subheader("🤖 Human Review")
        st.info("The agent is waiting for your feedback. You can approve the plan or request changes.")
        feedback = st.text_area("Your Feedback", placeholder="e.g., 'Add a museum visit on day 2' or 'Find a cheaper hotel'")
        
        col1, col2 = st.columns(2)
        if col1.button("Submit Feedback", type="primary"):
            if feedback:
                with st.spinner("Updating plan based on your feedback..."):
                    planner_app.update_state(config, {"user_feedback": feedback}, as_node="human_review")
                    planner_app.invoke(None, config)
                    st.session_state.current_state = planner_app.get_state(config)
                    st.rerun()
            else:
                st.error("Please enter some feedback.")
                
        if col2.button("Approve & Finish"):
            with st.spinner("Finalizing..."):
                planner_app.update_state(config, {"user_feedback": "APPROVE"}, as_node="human_review")
                planner_app.invoke(None, config)
                st.session_state.current_state = planner_app.get_state(config)
                st.rerun()
    else:
        st.balloons()
        st.success("Planning complete!")
else:
    st.info("Enter trip details in the sidebar and click 'Start New Planning' to begin.")
