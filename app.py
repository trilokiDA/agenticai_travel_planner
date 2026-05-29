import streamlit as st
import os
from graph import app
from state import AgentState
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="AI Travel Planner", page_icon="✈️")

st.title("✈️ AI Travel Planner")
st.markdown("Plan your next adventure with the help of AI agents!")

# Sidebar for inputs
with st.sidebar:
    st.header("Trip Details")
    destination = st.text_input("Destination", placeholder="e.g., Paris, Goa")
    origin = st.text_input("Origin", placeholder="e.g., London, Delhi")
    travel_date = st.date_input("Travel Date", value=None, help="Select your preferred travel month/year")
    budget = st.number_input("Budget", min_value=1.0, value=50000.0)
    currency = st.selectbox("Currency", options=["INR", "USD"], index=0)
    duration = st.slider("Duration (Days)", min_value=1, max_value=14, value=3)
    
    start_planning = st.button("Generate Plan")

if start_planning:
    if not destination or not origin or not travel_date:
        st.error("Please provide origin, destination, and travel date.")
    elif not os.environ.get("GROQ_API_KEY") or not os.environ.get("TAVILY_API_KEY"):
        st.error("API Keys missing! Check your .env file.")
    else:
        # Format date for the agent (e.g., "June 2026")
        formatted_date = travel_date.strftime("%B %Y")
        
        initial_state: AgentState = {
            "destination": destination,
            "origin": origin,
            "travel_date": formatted_date,
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

        status_container = st.container()
        itinerary_container = st.empty()
        
        with st.status("🤖 AI Agents are working...", expanded=True) as status:
            # We use stream to get updates from the graph nodes
            for event in app.stream(initial_state):
                for node, state in event.items():
                    if node == "researcher":
                        st.write(f"🔍 **Researcher** is finding options for {destination}...")
                        if state.get("search_queries"):
                            st.write("**Search Queries:**")
                            for q in state["search_queries"]:
                                st.write(f"- {q}")
                    
                    elif node == "planner":
                        st.write("📋 **Planner** is building your itinerary...")
                    
                    elif node == "validator":
                        st.write("✅ **Validator** is checking the budget and details...")
                        itinerary = state.get("current_itinerary")
                        if itinerary and itinerary.status == "Invalid":
                            st.warning(f"Validation Note: {itinerary.validation_notes}")
            
            status.update(label="✅ Planning Complete!", state="complete", expanded=False)

        # Final Itinerary Display
        # We need the final state to display the itinerary
        final_state = app.invoke(initial_state) # Note: invoking again for final result, ideally we'd capture state from stream
        itinerary = final_state.get("current_itinerary")

        if itinerary:
            st.success(f"### 🎊 Itinerary for {itinerary.destination}")
            
            col1, col2 = st.columns(2)
            col1.metric("Total Budget", f"{budget} {currency}")
            col2.metric("Total Cost", f"{itinerary.total_cost} {currency}")
            
            st.info(f"**Status:** {itinerary.status}")
            
            st.subheader("✈️ Flights")
            for f in itinerary.flights:
                st.write(f"**{f.provider}**: {f.origin} → {f.destination} (**{currency} {f.price}**)")
            
            st.subheader("🏨 Hotels")
            for h in itinerary.hotels:
                st.write(f"**{h.name}**: {currency} {h.price_per_night}/night (Total: **{currency} {h.total_price}**)")
                if h.rating:
                    st.write(f"⭐ Rating: {h.rating}")
            
            st.subheader("📅 Daily Schedule")
            # Group by day
            for day in range(1, duration + 1):
                day_activities = [a for a in itinerary.activities if a.day_number == day]
                if day_activities:
                    with st.expander(f"Day {day}"):
                        for a in day_activities:
                            st.write(f"📍 **{a.name}** - {a.description} ({currency} {a.cost})")
            
            if itinerary.validation_notes:
                st.markdown(f"**Notes:** {itinerary.validation_notes}")
        else:
            st.error("Failed to generate a valid itinerary. Try increasing the budget or destination details.")
