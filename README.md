# Synapse — The Enterprise Memory Layer

**Synapse** is an AI-powered "Enterprise Memory Layer" for production support teams. It's an intelligent assistant embedded in a realistic service desk console that helps agents resolve incidents faster by learning from historical data.

Built with FastAPI and vanilla JS, this prototype demonstrates how Google's Gemini API can power a grounded, context-aware RAG application in a real-world enterprise setting.

## Core Features

- **AI-Powered Suggestions:** Get grounded, step-by-step action plans for active incidents, based on a semantic search of past resolutions.
- **Proactive Pattern Detection:** Automatically identify and summarize emerging incident patterns directly in the main queue.
- **Realistic Service Desk UI:** A complete, production-grade console with a live queue, searchable knowledge base, and incident creation.
- **Live Knowledge Growth:** The system's memory grows with every resolved incident, making it smarter over time.
- **Built-in AI Guardrails:** Synapse won't hallucinate. If it doesn't have a confident answer, it says so plainly.

> **Note:** This prototype uses a synthetic dataset. No real customer or incident data is used.

## Quick Start

1.  **Clone & Setup:**
    ```bash
    git clone <repository-url>
    cd synapse-v2/backend
    pip install -r requirements.txt
    ```

2.  **Set API Key:**
    - Create a `.env` file in the `backend` directory.
    - Add your Google Gemini API key: `GOOGLE_API_KEY="YOUR_API_KEY_HERE"`

3.  **Generate Data & Run:**
    ```bash
    python data/seed_incidents.py
    uvicorn main:app --reload
    ```

4.  Open **http://localhost:8000**.

## Demo Flow

1.  **Pattern Detection:** On the **Incident Queue**, note the banner flagging a pattern across several ETL jobs.
2.  **Strong Match:** Click **INC0010026** (`ETL_LoadVendorPricing...`) and **Ask Synapse** for a confident, AI-generated fix.
3.  **Guardrail Test:** Click **INC0010030** (`Dashboard shows inconsistent...`) and **Ask Synapse**. It will correctly state no precedent was found.
4.  **Live Learning:** Resolve an incident. The "Knowledge base" count in the sidebar will increase instantly.

## Technology Stack

- **Backend:** FastAPI, Uvicorn, Gunicorn
- **Frontend:** HTML5, CSS3, JavaScript (no frameworks)
- **AI & Data Science:** Google Gemini API, Scikit-learn, NumPy

## Project Layout

```plaintext
backend/
  main.py                  # FastAPI app: mock incident API + Synapse AI endpoints
  gemini_service.py         # Wrapper for Google Gemini API (embeddings & generation)
  data/
    incidents.json            # The synthetic incident dataset
    seed_incidents.py          # Script to generate a fresh `incidents.json` file
  static/
    index.html, styles.css, app.js    # The console frontend
  .env                     # For storing the GOOGLE_API_KEY (not checked into git)
  requirements.txt         # Python package dependencies
```
