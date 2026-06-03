# ✈️ AI Travel Planner

An AI-powered travel planner that orchestrates a research-plan-validate loop using LangGraph to create structured, budget-conscious travel itineraries.

## 🚀 Overview

This project utilizes a **Multi-Agent Orchestration** workflow to provide realistic travel plans:
- **🔍 Researcher**: Dynamically generates search queries and fetches real-time data for flights, hotels, and activities using the **Tavily API**.
- **📋 Planner**: Processes raw search data into a structured itinerary using **Llama 3.3 (via Groq)**.
- **✅ Validator**: Cross-checks the generated plan against the user's budget and requirements, triggering re-research if necessary.

## ✨ Key Features

- **Dynamic Trip Selection**: Choose between **Round Trip** and **One Way** journeys.
- **Smart Date Handling**: Automatically calculates trip duration based on start/end dates.
- **Currency Support**: Plan your trip in **INR** or **USD**.
- **Budget Validation**: Ensures total costs (flights + hotels + activities) stay within your specified limit.
- **Performance Caching**: Uses **Streamlit Caching** to provide instant results for repeated searches and minimize API costs.
- **Rich UI**: Interactive dashboard built with **Streamlit** for a seamless planning experience.

## 📁 Project Structure

```text
travel_planner/v1/
├── app.py           # Streamlit Web Interface
├── main.py          # CLI Entry point
├── graph.py         # LangGraph state machine & AI logic
├── models.py        # Pydantic data models (Itinerary, Flight, etc.)
├── state.py         # Agent state schema
├── tools.py         # Search tool integration (Tavily)
├── .env             # API Key configuration
└── requirements.txt # Project dependencies
```

## 🛠️ Setup & Installation

1. **Environment Variables**:
   Create a `.env` file in the root directory with your API keys:
   ```env
   GROQ_API_KEY=your_groq_api_key
   TAVILY_API_KEY=your_tavily_api_key
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 🖥️ Usage

### 🌐 Web Interface (Recommended)
Launch the interactive dashboard:
```bash
streamlit run app.py
```

### 💻 CLI Mode
Run the planner directly from the terminal using the example configuration in `main.py`:
```bash
python main.py
```

## 🧠 Technical Highlights

- **LangGraph**: Manages the complex cycle of research and planning.
- **Llama 3.3 (Groq)**: High-speed, high-quality reasoning for structured itinerary generation.
- **Pydantic**: Ensures strict data integrity for all output models.
- **Robust Parsing**: Includes regex-based JSON extraction to handle varied LLM responses gracefully.
