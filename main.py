"""
Synapse backend — a mock ServiceNow-style incident API, plus the Synapse
AI endpoints (suggest / resolve / patterns) layered on top.

Run with:
    uvicorn main:app --reload

Then open http://localhost:8000 in a browser.

This mocks the SHAPE of a real ITSM Table API (incidents with number,
short_description, priority, state, assignment_group, etc.) so that
pointing Synapse at a real ServiceNow instance later is a data-source
swap, not a redesign.
"""
import json
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

import gemini_service

BASE_DIR = os.path.dirname(__file__)
INCIDENTS_PATH = os.path.join(BASE_DIR, "data", "incidents.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

ACTIVE_STATES = {"New", "In Progress"}
TOP_K = 3
CONFIDENCE_THRESHOLD = 0.72
PATTERN_THRESHOLD = 0.80

# ---------- in-memory state ----------

state = {
    "incidents": [],       # list[dict], full incident table
    "kb_ids": [],           # sys_id, aligned with kb_embeddings rows
    "kb_embeddings": None,  # np.ndarray or None
    "kb_ready": False,
    "kb_error": None,
}


def problem_text(incident: dict) -> str:
    return f"{incident['short_description']}. {incident['description']}"


def load_incidents():
    with open(INCIDENTS_PATH) as f:
        state["incidents"] = json.load(f)


def save_incidents():
    with open(INCIDENTS_PATH, "w") as f:
        json.dump(state["incidents"], f, indent=2)


def build_knowledge_base():
    closed = [i for i in state["incidents"] if i["state"] == "Closed"]
    try:
        texts = [problem_text(i) for i in closed]
        embeddings = gemini_service.embed_documents(texts)
        state["kb_ids"] = [i["sys_id"] for i in closed]
        state["kb_embeddings"] = embeddings
        state["kb_ready"] = True
        state["kb_error"] = None
    except Exception as exc:  # noqa: BLE001 — surface any failure to the API instead of crashing startup
        state["kb_ready"] = False
        state["kb_error"] = str(exc)


def get_incident(number: str) -> dict:
    for i in state["incidents"]:
        if i["number"] == number:
            return i
    raise HTTPException(status_code=404, detail=f"No incident found with number {number}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_incidents()
    build_knowledge_base()
    yield


app = FastAPI(title="Synapse Incident API", lifespan=lifespan)


# ---------- request/response models ----------

class ResolveRequest(BaseModel):
    close_notes: str
    resolved_by: str


class CreateIncidentRequest(BaseModel):
    short_description: str
    description: str
    priority: str
    assignment_group: str
    category: str
    opened_by: str


# ---------- API routes ----------

@app.get("/api/stats")
def get_stats():
    return {
        "kb_size": len(state["kb_ids"]),
        "kb_ready": state["kb_ready"],
        "kb_error": state["kb_error"],
        "total_incidents": len(state["incidents"]),
    }


@app.get("/api/incidents/queue")
def get_queue():
    return [i for i in state["incidents"] if i["state"] in ACTIVE_STATES]


@app.get("/api/incidents/history")
def get_history():
    closed = [i for i in state["incidents"] if i["state"] not in ACTIVE_STATES]
    return sorted(closed, key=lambda i: i["resolved_at"] or "", reverse=True)


@app.get("/api/meta/form-options")
def get_form_options():
    """Return unique values for form dropdowns."""
    incidents = state["incidents"]
    return {
        "assignment_groups": sorted(list({i["assignment_group"] for i in incidents})),
        "categories": sorted(list({i["category"] for i in incidents if i.get("category")})),
    }


@app.get("/api/search")
def search_incidents(q: str):
    """Search for incidents by number or keywords."""
    if not q:
        return []
    q_lower = q.lower()
    results = []
    for i in state["incidents"]:
        if q_lower in i["number"].lower() or q_lower in i["short_description"].lower() or q_lower in i["description"].lower():
            results.append(i)
    return sorted(results, key=lambda i: i["opened_at"] or "", reverse=True)


@app.get("/api/incidents/{number}")
def get_one(number: str):
    return get_incident(number)


@app.post("/api/incidents", status_code=201)
def create_incident(body: CreateIncidentRequest):
    now = datetime.now(timezone.utc)
    if body.priority == "P1":
        sla_due = now + timedelta(hours=8)
    else:
        sla_due = now + timedelta(hours=24)

    # Find the max incident number to increment it
    max_n = 0
    for inc in state["incidents"]:
        with suppress(ValueError, TypeError):
            num_part = int(inc["number"].replace("INC", ""))
            if num_part > max_n:
                max_n = num_part

    new_n = max_n + 1
    new_incident = {
        "sys_id": f"sys{new_n:08d}",
        "number": f"INC{new_n:07d}",
        "short_description": body.short_description,
        "description": body.description,
        "category": body.category,
        "priority": body.priority,
        "state": "New",
        "assignment_group": body.assignment_group,
        "opened_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sla_due": sla_due.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "opened_by": body.opened_by,
    }
    state["incidents"].append(new_incident)
    save_incidents()
    return new_incident


@app.post("/api/incidents/{number}/suggest")
def suggest(number: str):
    if not state["kb_ready"]:
        raise HTTPException(
            status_code=503,
            detail=f"Synapse's knowledge base isn't ready: {state['kb_error']}",
        )

    incident = get_incident(number)
    query_text = problem_text(incident)
    query_vec = gemini_service.embed_query(query_text).reshape(1, -1)

    sims = cosine_similarity(query_vec, state["kb_embeddings"])[0]
    order = np.argsort(sims)[::-1][:TOP_K]

    matches = []
    for idx in order:
        sys_id = state["kb_ids"][idx]
        past = next(i for i in state["incidents"] if i["sys_id"] == sys_id)
        matches.append({"score": float(sims[idx]), "incident": past})

    best_score = matches[0]["score"] if matches else 0.0

    if best_score < CONFIDENCE_THRESHOLD:
        return {
            "confident": False,
            "suggestion": None,
            "matches": [],
        }

    suggestion_text = gemini_service.generate_action_plan(query_text, matches)

    return {
        "confident": True,
        "suggestion": suggestion_text,
        "matches": [
            {
                "number": m["incident"]["number"],
                "score": m["score"],
                "category": m["incident"]["category"],
                "short_description": m["incident"]["short_description"],
                "root_cause": m["incident"]["root_cause"],
                "close_notes": m["incident"]["close_notes"],
                "resolved_by": m["incident"]["resolved_by"],
            }
            for m in matches
        ],
    }


@app.post("/api/incidents/{number}/resolve")
def resolve(number: str, body: ResolveRequest):
    incident = get_incident(number)
    if incident["state"] not in ACTIVE_STATES:
        raise HTTPException(status_code=400, detail="Incident is already resolved.")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    incident["state"] = "Resolved"
    incident["resolved_at"] = now
    incident["resolved_by"] = body.resolved_by
    incident["close_notes"] = body.close_notes
    if not incident.get("root_cause"):
        incident["root_cause"] = "Determined during resolution — see close notes."

    save_incidents()

    # Grow Synapse's memory live, in front of the audience.
    try:
        vec = gemini_service.embed_documents([problem_text(incident)])
        if state["kb_embeddings"] is None or len(state["kb_ids"]) == 0:
            state["kb_embeddings"] = vec
        else:
            state["kb_embeddings"] = np.vstack([state["kb_embeddings"], vec])
        state["kb_ids"].append(incident["sys_id"])
    except Exception as exc:  # noqa: BLE001
        # Resolution still succeeds even if the live re-embed hiccups.
        state["kb_error"] = f"Last KB update failed: {exc}"

    return incident


@app.get("/api/patterns")
def get_patterns():
    active = [i for i in state["incidents"] if i["state"] in ACTIVE_STATES]
    if len(active) < 2 or not state["kb_ready"]:
        return {"groups": []}

    texts = [i["short_description"] for i in active]
    try:
        vectors = gemini_service.embed_for_clustering(texts)
    except Exception:
        return {"groups": []}

    # Use a more robust clustering algorithm that doesn't "daisy-chain".
    # This finds tight clusters where all members are similar to each other.
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1 - PATTERN_THRESHOLD,  # threshold is on similarity, so we convert to distance
        metric="cosine",
        linkage="average",
    ).fit(vectors)

    clusters = {}
    for idx, label in enumerate(clustering.labels_):
        clusters.setdefault(label, []).append(active[idx])

    groups = []
    for members in clusters.values():
        if len(members) >= 2:
            try:
                explanation = gemini_service.generate_pattern_summary(members)
            except Exception:
                explanation = "These incidents look related, but Synapse couldn't generate an explanation right now."
            groups.append({
                "incident_numbers": [m["number"] for m in members],
                "explanation": explanation,
            })

    return {"groups": groups}


# ---------- static frontend (mounted LAST so /api/* routes above take precedence) ----------

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
