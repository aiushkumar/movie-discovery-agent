"""
gemini_service.py

All Gemini LLM interactions for Movie Discovery Agent 2.0.

Responsibilities:
  - parse_intent()              : Understand natural language query -> structured intent
  - explain_movie()             : Personalised reason why a movie was chosen
  - summarise_memory()          : Summarise what the agent has learned from feedback
  - explain_feedback_learning() : What the agent learned from a rejection
"""

import json
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(override=False)

_API_KEY = os.getenv("GEMINI_API_KEY")
_MODEL         = "gemini-flash-latest"   # alias always resolves to current available flash model
_MODEL_FALLBACK = "gemini-3.1-flash-lite"  # confirmed working fallback
_client  = None


def _get_client() -> genai.Client:
    """Lazy-initialise the Gemini client once."""
    global _client
    if _client is None:
        if not _API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Add it to your .env file or "
                "Hugging Face Secrets."
            )
        _client = genai.Client(api_key=_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# JSON utilities
# ---------------------------------------------------------------------------

def _clean_json(raw: str) -> str:
    """
    Robustly clean LLM JSON output before parsing.

    Handles:
    - Markdown fences (```json ... ```)
    - Inline // comments
    - Trailing commas before } or ]
    """
    # Strip markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        # grab everything between first and last fence
        inner = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        inner = re.sub(r"\n?```$", "", inner)
        raw = inner.strip()

    # Remove // inline comments (not valid JSON)
    raw = re.sub(r"//[^\n]*", "", raw)

    # Remove trailing commas before } or ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    return raw.strip()


def _parse_json_safe(raw: str) -> dict | None:
    """Try to parse JSON after cleaning. Returns None on failure."""
    try:
        return json.loads(_clean_json(raw))
    except (json.JSONDecodeError, ValueError):
        return None


def _fallback_extract(raw: str, query: str) -> dict:
    """
    Last-resort extraction using regex when JSON is completely malformed.
    Pulls whatever fields we can from the raw text.
    """
    result: dict = {}

    # genres
    m = re.search(r'"genres"\s*:\s*\[([^\]]*)\]', raw)
    if m:
        result["genres"] = [g.strip().strip('"') for g in m.group(1).split(",") if g.strip()]

    # mood
    m = re.search(r'"mood"\s*:\s*"([^"]+)"', raw)
    if m:
        result["mood"] = m.group(1)

    # year
    m = re.search(r'"year"\s*:\s*(\d{4})', raw)
    if m:
        result["year"] = int(m.group(1))
    else:
        # try to find a year in the original query
        m = re.search(r'\b(19\d{2}|20\d{2})\b', query)
        if m:
            result["year"] = int(m.group(1))

    # sort_by
    if any(kw in query.lower() for kw in ("best", "top", "highest rated")):
        result["sort_by"] = "vote_average.desc"
    else:
        result["sort_by"] = "popularity.desc"

    # similar_to
    m = re.search(r'"similar_to"\s*:\s*\[([^\]]*)\]', raw)
    if m:
        result["similar_to"] = [g.strip().strip('"') for g in m.group(1).split(",") if g.strip()]

    # understanding_bullets — build minimal ones from what we extracted
    bullets = []
    for g in result.get("genres", []):
        bullets.append(f"Genre: {g.title()}")
    if result.get("mood"):
        bullets.append(f"Mood: {result['mood']}")
    if result.get("year"):
        bullets.append(f"Released after {result['year']}")
    if result.get("similar_to"):
        bullets.append(f"Similar to: {', '.join(result['similar_to'])}")
    if bullets:
        result["understanding_bullets"] = bullets

    return result


# ---------------------------------------------------------------------------
# Phase 1 — Intent parsing
# ---------------------------------------------------------------------------

_INTENT_PROMPT = """\
You are a movie recommendation assistant.
Extract the user's intent from the query below as a JSON object.

IMPORTANT: Return ONLY a raw JSON object. No markdown, no code fences, no comments.

Required JSON shape (use null for missing fields):
{{
  "genres": [],
  "mood": null,
  "similar_to": [],
  "themes": [],
  "era": null,
  "year": null,
  "language": null,
  "family_friendly": null,
  "viewing_context": null,
  "sort_by": "popularity.desc",
  "understanding_bullets": []
}}

Rules:
- "genres" must be lowercase strings from: action, adventure, animation, comedy, crime, documentary, drama, family, fantasy, history, horror, mystery, romance, science fiction, thriller, war, western
- "sort_by" is "vote_average.desc" if user says best/top/highest rated, else "popularity.desc"
- "year" must be an integer (e.g. 2018) or null — never a string
- "understanding_bullets" are 3-6 short plain English phrases shown to the user

User query: {query}
"""


def parse_intent(query: str) -> dict:
    """
    Use Gemini to extract structured intent from a natural language query.

    Args:
        query: Raw user input

    Returns:
        dict with intent fields. Guaranteed to return a dict (never raises).
    """
    client = _get_client()
    prompt = _INTENT_PROMPT.format(query=query)

    raw_response = ""

    # --- Attempt 1: primary model ---
    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=600,
            ),
        )
        raw_response = response.text.strip()
        result = _parse_json_safe(raw_response)
        if result and isinstance(result, dict):
            return result
    except Exception as exc:
        print(f"[gemini_service] parse_intent attempt 1 error: {exc}")

    # --- Attempt 2: fallback model + stricter prompt ---
    time.sleep(1)
    retry_prompt = (
        f'Return ONLY a JSON object with no comments or extra text.\n\n'
        f'Extract movie preferences from: "{query}"\n\n'
        f'JSON keys: genres (list), mood (str), similar_to (list), '
        f'themes (list), year (int or null), sort_by (str), '
        f'understanding_bullets (list of short strings).'
    )
    try:
        response = client.models.generate_content(
            model=_MODEL_FALLBACK,
            contents=retry_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=400,
            ),
        )
        raw_response = response.text.strip()
        result = _parse_json_safe(raw_response)
        if result and isinstance(result, dict):
            print("[gemini_service] parse_intent succeeded on retry")
            return result
    except Exception as exc:
        print(f"[gemini_service] parse_intent attempt 2 error: {exc}")

    # --- Fallback: regex extraction ---
    print("[gemini_service] parse_intent using fallback extraction")
    return _fallback_extract(raw_response, query)


# ---------------------------------------------------------------------------
# Phase 4 — Per-movie explanations
# ---------------------------------------------------------------------------

def explain_movie(movie: dict, intent: dict) -> str:
    """
    Generate a personalised reason why this specific movie was recommended.

    Returns one short paragraph. Empty string on any error.
    """
    client = _get_client()

    title        = movie.get("title", "Unknown")
    overview     = movie.get("overview", "")
    release_date = movie.get("release_date", "")
    rating       = movie.get("vote_average", "")
    mood         = intent.get("mood", "")
    similar      = ", ".join(intent.get("similar_to") or [])
    themes       = ", ".join(intent.get("themes") or [])
    genres       = ", ".join(intent.get("genres") or [])

    prompt = (
        f'Movie: {title}\n'
        f'Overview: {overview}\n'
        f'Release: {release_date}  Rating: {rating}\n\n'
        f'User wanted: genres={genres}, mood={mood}, '
        f'similar to={similar}, themes={themes}\n\n'
        f'Write 2-3 sentences explaining why {title} matches the user\'s request. '
        f'Be specific. Do not copy the overview verbatim. '
        f'Return only the explanation — no labels, no headings.'
    )

    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=180,
            ),
        )
        return response.text.strip()
    except Exception:
        try:
            response = client.models.generate_content(
                model=_MODEL_FALLBACK,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=180),
            )
            return response.text.strip()
        except Exception as exc:
            print(f"[gemini_service] explain_movie failed: {exc}")
            return ""


# ---------------------------------------------------------------------------
# Phase 5 — Memory summary
# ---------------------------------------------------------------------------

def summarise_memory(records: list) -> dict:
    """
    Summarise what the agent has learned from past feedback.

    Returns dict with keys "likes" and "dislikes" (lists of short strings).
    """
    if not records:
        return {"likes": [], "dislikes": []}

    client   = _get_client()
    records_text = json.dumps(records, indent=2)

    prompt = (
        f'Here is a user\'s movie feedback history:\n{records_text}\n\n'
        f'Return ONLY a JSON object (no comments, no fences) with:\n'
        f'{{"likes": ["short phrase", ...], "dislikes": ["short phrase", ...]}}\n\n'
        f'Each item should be 3-7 words describing themes/genres/tones, not movie titles.'
    )

    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=300,
            ),
        )
        raw = response.text.strip()
        result = _parse_json_safe(raw)
        if result and isinstance(result, dict):
            return result
    except Exception:
        pass

    # Retry with fallback model
    try:
        response = client.models.generate_content(
            model=_MODEL_FALLBACK,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=300,
            ),
        )
        raw = response.text.strip()
        result = _parse_json_safe(raw)
        if result and isinstance(result, dict):
            return result
    except Exception as exc:
        print(f"[gemini_service] summarise_memory failed: {exc}")

    return {"likes": [], "dislikes": []}


# ---------------------------------------------------------------------------
# Phase 6 — Feedback learning message
# ---------------------------------------------------------------------------

def explain_feedback_learning(movie_title: str, reason: str) -> str:
    """
    Generate 2-3 bullet points explaining what the agent learned from a rejection.
    """
    client = _get_client()

    prompt = (
        f'A user rejected "{movie_title}" because: "{reason}"\n\n'
        f'Write 2-3 short bullet points (starting with "- ") explaining what '
        f'the recommendation system learned. Be specific to the reason. '
        f'Return only the bullet points.'
    )

    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=150,
            ),
        )
        return response.text.strip()
    except Exception as exc:
        print(f"[gemini_service] explain_feedback_learning failed: {exc}")
        return "- Preference recorded\n- Will avoid similar recommendations"
