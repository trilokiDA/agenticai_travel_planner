import streamlit as st
import os
import uuid
import json
from state import AgentState
from models import Itinerary, Flight, Hotel, Activity
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any
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

st.title("✈️ AI Travel Planner")
st.markdown("Plan your next adventure with Human-in-the-loop AI agents!")

# PERSISTENCE FIX: Cache the entire app AND its checkpointer to survive Streamlit reruns
@st.cache_resource
def get_planner_app():
    from graph import workflow
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

# Sidebar for inputs
with st.sidebar:
    st.header("Trip Details")
    destination = st.text_input("Destination", placeholder="Paris, Goa", key="dest")
    origin = st.text_input("Origin", placeholder="London, Delhi", key="orig")
    
    trip_type = st.radio("Trip Type", ["Round Trip", "One Way"], index=0)
    
    if trip_type == "Round Trip":
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start Date", value=None, min_value=today)
        end_date = col2.date_input("End Date", value=None, min_value=start_date if start_date else today)
        duration = (end_date - start_date).days + 1 if start_date and end_date else 0
        is_round_trip = True
    else:
        start_date = st.date_input("Start Date", value=None, min_value=today)
        duration = st.slider("Duration (Days)", min_value=1, max_value=14, value=3)
        is_round_trip = False
        
    budget = st.number_input("Budget", min_value=1.0, value=50000.0)
    currency = st.selectbox("Currency", options=["INR", "USD"], index=0)
    
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
            with st.spinner("Researching and planning..."):
                planner_app.invoke(initial_state, config)
                st.session_state.current_state = planner_app.get_state(config)

# Helper to display itinerary
def display_itinerary_ui(itinerary: Itinerary, budget: float, currency: str, duration: int):
    st.success(f"### 🎊 Itinerary for {itinerary.destination}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Budget", f"{budget} {currency}")
    col2.metric("Total Cost", f"{itinerary.total_cost} {currency}")
    col3.metric("Status", itinerary.status)
    
    if itinerary.validation_notes:
        st.warning(f"**Validation Notes:** {itinerary.validation_notes}")
    
    tab1, tab2, tab3 = st.tabs(["✈️ Flights", "🏨 Hotels", "📅 Daily Schedule"])
    
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
            if day_activities:
                with st.expander(f"Day {day}"):
                    for a in day_activities:
                        st.write(f"📍 **{a.name}** - {a.description} (**{currency} {a.cost}**)")

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
            state_values.get('duration_days', 1)
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
