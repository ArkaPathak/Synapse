"""
Thin wrapper around the Gemini API (new google-genai SDK): embeddings for
semantic search over the incident knowledge base, and grounded generation
for the Suggested Action Plan / pattern explanations.
"""
import os
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

EMBEDDING_MODEL = "gemini-embedding-001"
GENERATION_MODEL = "gemini-flash-latest"  # Google-maintained alias for their current recommended Flash model

_client: Optional[genai.Client] = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Copy .env.example to .env in the "
                "backend/ folder and paste in a free key from https://aistudio.google.com/"
            )
        _client = genai.Client(api_key=api_key)
    return _client


def embed_documents(texts: list[str]) -> np.ndarray:
    """Embed a batch of historical-incident texts for retrieval."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    result = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return np.array([e.values for e in result.embeddings], dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    """Embed a single new-incident text for searching against the knowledge base."""
    result = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return np.array(result.embeddings[0].values, dtype=np.float32)


def embed_for_clustering(texts: list[str]) -> np.ndarray:
    """Embed active-incident texts for pattern clustering (symmetric comparison,
    so both sides use the same task type)."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    result = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
    )
    return np.array([e.values for e in result.embeddings], dtype=np.float32)


def generate_action_plan(new_incident_text: str, matches: list[dict]) -> str:
    context_blocks = []
    for m in matches:
        r = m["incident"]
        context_blocks.append(
            f"- Past incident {r['number']} (similarity {m['score']:.2f}, category: {r['category']})\n"
            f"  Short description: {r['short_description']}\n"
            f"  Root cause: {r['root_cause']}\n"
            f"  Resolution: {r['close_notes']}\n"
            f"  Resolved by: {r['resolved_by']}"
        )
    context = "\n".join(context_blocks)

    prompt = f"""You are Synapse, an AI assistant embedded in a production-support service desk.
Draft a short, practical Suggested Action Plan for a NEW incident, grounded
ONLY in the past incidents provided below. Do not invent facts that aren't
supported by the past incidents. If they don't really match, say so plainly.

NEW INCIDENT:
{new_incident_text}

MOST SIMILAR PAST INCIDENTS (from resolved-incident history):
{context}

Write a Suggested Action Plan with exactly three short sections:
1. Likely Root Cause — one or two sentences, referencing which past incident(s) support this.
2. Recommended Fix — concrete, step-by-step, based on what worked before.
3. Confidence & Caveats — one sentence on how strong this match is and what to double-check.

Keep the whole answer under 150 words. Plain text, no markdown headers, just the three numbered sections."""

    response = get_client().models.generate_content(model=GENERATION_MODEL, contents=prompt)
    return response.text


def generate_pattern_summary(incidents: list[dict]) -> str:
    listing = "\n".join(
        f"- {i['number']}: {i['short_description']} — {i['description']}" for i in incidents
    )
    prompt = f"""You are Synapse, an AI assistant embedded in a production-support service desk.
The following currently-open incidents look related. In under 40 words, state
the most likely shared root cause in plain language, referencing the incident
numbers. If you are not confident they share a cause, say that instead.

INCIDENTS:
{listing}"""
    response = get_client().models.generate_content(model=GENERATION_MODEL, contents=prompt)
    return response.text
