# Travel Planner v1

An AI-powered travel planner that orchestrates a research-plan-validate loop to create structured travel itineraries based on user constraints.

## Overview

This project uses **LangGraph** to manage a multi-agent workflow:
- **Researcher**: Generates search queries and fetches travel data using the **Tavily API**.
- **Planner**: Parses raw data into a structured itinerary using a Large Language Model (via **Groq**).
- **Validator**: Checks the itinerary against the user's budget and ensures all necessary components (flights, hotels, activities) are present.

## Features

- **Multi-Agent Orchestration**: Sequential and conditional logic to refine plans until they meet criteria.
- **Structured Output**: Uses Pydantic models for consistent and type-safe itinerary data.
- **Web Search Integration**: Real-time travel information retrieval.
- **Budget Tracking**: Automatic cost calculation and validation.

## Project Structure

```text
travel_planner/v1/
├── main.py        # Entry point to run the planner
├── graph.py       # LangGraph state machine definition
├── models.py      # Pydantic data models (Itinerary, Flight, etc.)
├── state.py       # Agent state schema
├── tools.py       # Search tool integration (Tavily)
└── requirements.txt # Project dependencies
```

## Setup

1. **Environment Variables**:
   Create a `.env` file in the `travel_planner/v1` directory with your API keys:
   ```env
   GROQ_API_KEY=your_groq_api_key
   TAVILY_API_KEY=your_tavily_api_key
   ```

2. **Install Dependencies**:
   It is recommended to use a virtual environment.
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the planner using the example configuration in `main.py`:

```bash
python main.py
```

You can modify the `run_planner` call at the bottom of `main.py` to change the destination, origin, budget, or duration.
