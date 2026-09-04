import sys
from pathlib import Path

# Make src/movie_discovery importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "movie_discovery"))

import streamlit as st
from feedback_memory import load_all_records, load_rejected_titles, process_feedback
from gemini_service import (
    explain_feedback_learning,
    explain_movie,
    parse_intent,
    summarise_memory,
)
from tmdb_service import discover_movies, parse_query

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Movie Discovery Agent",
    page_icon="🎬",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Dark cinematic background — Batman-inspired Gotham cityscape
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp {
        background-image:
            linear-gradient(rgba(5, 5, 15, 0.83), rgba(5, 5, 15, 0.83)),
            url("https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1920&q=80");
        background-size: cover;
        background-position: center top;
        background-repeat: no-repeat;
        background-attachment: scroll;
    }

    .block-container {
        background: rgba(10, 10, 20, 0.60) !important;
        border-radius: 12px;
        padding: 2.5rem 3rem !important;
        backdrop-filter: blur(3px);
        -webkit-backdrop-filter: blur(3px);
    }

    [data-testid="stSidebar"] {
        background: rgba(8, 8, 18, 0.92) !important;
        border-right: 1px solid rgba(255, 200, 0, 0.15);
    }

    h1, h2, h3 {
        color: #f5f0e0 !important;
        letter-spacing: 0.02em;
    }

    p, li, label, .stCaption, .stMarkdown {
        color: #d0ccc0 !important;
    }

    [data-testid="stMetricLabel"]  { color: #b0aa99 !important; }
    [data-testid="stMetricValue"]  { color: #f5e97a !important; }

    .stTextInput > div > div > input {
        background-color: rgba(20, 20, 35, 0.85) !important;
        color: #f0ece0 !important;
        border: 1px solid rgba(255, 200, 0, 0.3) !important;
        border-radius: 6px;
    }

    .stButton > button {
        background-color: rgba(200, 160, 0, 0.88) !important;
        color: #0a0a0f !important;
        font-weight: 700;
        border: none;
        border-radius: 6px;
        transition: background-color 0.2s ease;
    }
    .stButton > button:hover {
        background-color: rgba(230, 190, 20, 1) !important;
    }

    hr { border-color: rgba(255, 200, 0, 0.2) !important; }

    /* AI badge */
    .ai-badge {
        display: inline-block;
        background: rgba(200, 160, 0, 0.18);
        border: 1px solid rgba(200, 160, 0, 0.45);
        border-radius: 20px;
        padding: 2px 12px;
        font-size: 0.75rem;
        color: #f5e97a;
        margin-left: 8px;
        vertical-align: middle;
    }

    /* Section cards */
    .section-card {
        background: rgba(15, 15, 30, 0.55);
        border: 1px solid rgba(255, 200, 0, 0.12);
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Phase 8 — Homepage title + subtitle
# ---------------------------------------------------------------------------

st.title("🎬 AI Movie Discovery Agent")
st.markdown(
    """
    Discover movies through **AI-powered understanding**,
    reasoning,
    and learning memory.
    """
)

# Workflow banner
st.markdown(
    """
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;
                margin:0.6rem 0 1.2rem 0;font-size:0.85rem;color:#b0aa99;
                background:rgba(15,15,30,0.5);border-radius:8px;padding:0.6rem 1rem;
                border:1px solid rgba(255,200,0,0.1);">
      <span>🗣 User Request</span>
      <span style="color:#555;">→</span>
      <span style="color:#f5e97a;font-weight:600;">🤖 AI Understanding</span>
      <span style="color:#555;">→</span>
      <span>🔍 TMDB Search</span>
      <span style="color:#555;">→</span>
      <span style="color:#f5e97a;font-weight:600;">💡 AI Reasoning</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ---------------------------------------------------------------------------
# Phase 3 — Task 1: Visible Memory (main page, above search)
# ---------------------------------------------------------------------------

all_records_pre = load_all_records()

if all_records_pre:
    st.markdown("### 🧠 What I've Learned About You")
    st.caption("Based on your previous feedback")

    with st.container(border=True):
        with st.spinner("Reading your memory..."):
            memory_summary = summarise_memory(all_records_pre)

        likes    = memory_summary.get("likes") or []
        dislikes = memory_summary.get("dislikes") or []

        col_likes, col_avoid = st.columns(2)

        with col_likes:
            st.markdown("**Likes:**")
            if likes:
                for item in likes:
                    st.markdown(f"- {item}")
            else:
                st.caption("Nothing detected yet.")

        with col_avoid:
            st.markdown("**Avoid:**")
            if dislikes:
                for item in dislikes:
                    st.markdown(f"- {item}")
            else:
                st.caption("Nothing detected yet.")

    st.divider()

# ---------------------------------------------------------------------------
# Section 1 — Search input
# ---------------------------------------------------------------------------

st.header("🔍 Find Movies")

query = st.text_input(
    "Which movie genre you want to watch movie from?",
    placeholder="e.g. something like Interstellar but less depressing after 2018",
)

if st.button("Get Recommendations", use_container_width=False):
    if not query.strip():
        st.warning("Please enter a query before searching.")
    else:

        # ---------------------------------------------------------------
        # Phase 1 — Gemini intent parsing
        # ---------------------------------------------------------------
        with st.spinner("🤖 Gemini is understanding your request..."):
            intent = parse_intent(query)

        # Fall back to deterministic parse_query if Gemini returns nothing useful
        if not intent or (not intent.get("genres") and not intent.get("year")):
            intent_display = parse_query(query)
            intent.update({
                "genres": [intent_display["genre"]] if intent_display.get("genre") else [],
                "year": intent_display.get("year"),
                "sort_by": intent_display.get("sort_by", "popularity.desc"),
                "understanding_bullets": [
                    f"Genre: {intent_display['genre'].title()}" if intent_display.get("genre") else "Genre: Not detected",
                    f"Year: after {intent_display['year']}" if intent_display.get("year") else "Year: Any",
                ],
            })

        # ---------------------------------------------------------------
        # Phase 2 — Visible AI Understanding
        # ---------------------------------------------------------------
        st.markdown("### 🧠 AI Understanding")
        st.caption("Here's what I understood from your request")

        bullets = intent.get("understanding_bullets") or []
        with st.container(border=True):
            if bullets:
                for b in bullets:
                    st.markdown(f"• {b}")
            else:
                st.caption("_(Could not extract structured understanding from query)_")

        # ---------------------------------------------------------------
        # Phase 3 — Visible AI Search Strategy
        # ---------------------------------------------------------------
        st.markdown("### 🎯 AI Search Strategy")
        st.caption("How Gemini translated your request into a TMDB search")

        with st.container(border=True):
            # Row 1: Genre | Mood | Release Year | Sort
            col1, col2, col3, col4 = st.columns(4)
            genres_list = intent.get("genres") or []
            col1.metric("Genre",        genres_list[0].title() if genres_list else "Any")
            col2.metric("Mood",         intent.get("mood") or "Not specified")
            col3.metric("Release Year", f"{intent.get('year')}+" if intent.get("year") else "Any")
            sort_label = "By Rating" if intent.get("sort_by") == "vote_average.desc" else "By Popularity"
            col4.metric("Sort",         sort_label)

            # Row 2: Similar Movies | Themes (only if present)
            similar  = intent.get("similar_to") or []
            themes   = intent.get("themes") or []
            language = intent.get("language")

            if similar or themes or language:
                st.markdown("")   # spacing
                col5, col6, col7 = st.columns(3)
                col5.metric("Similar Movies", ", ".join(similar) if similar else "—")
                col6.metric("Themes",         ", ".join(t.title() for t in themes) if themes else "—")
                col7.metric("Language",       language.title() if language else "Any")

        # ---------------------------------------------------------------
        # TMDB fetch
        # ---------------------------------------------------------------
        with st.spinner("🔍 Searching TMDB..."):
            movies = discover_movies(intent)

        # ---------------------------------------------------------------
        # Phase 3 — Task 3: Personalization label
        # ---------------------------------------------------------------
        rejected = load_rejected_titles()
        if rejected:
            st.info(
                f"🎯 **Personalized Using Your History** — "
                f"{len(rejected)} rejected movie(s) excluded from results."
            )

        # ---------------------------------------------------------------
        # Phase 4 — Recommendations with AI explanations
        # ---------------------------------------------------------------
        st.markdown("### 🎬 Top Recommendations")

        if not movies:
            st.info(
                "No recommendations found. Try a different query, "
                "or some results may have been filtered by your memory."
            )
        else:
            for movie in movies:
                title       = movie.get("title", "Unknown")
                release_date = movie.get("release_date", "N/A")
                rating      = movie.get("vote_average", "N/A")
                overview    = movie.get("overview", "")

                with st.container(border=True):
                    col_title, col_meta = st.columns([3, 1])
                    with col_title:
                        st.markdown(f"**{title}**")
                    with col_meta:
                        st.caption(f"📅 {release_date}  ⭐ {rating}")

                    if overview:
                        st.caption(overview[:220] + ("..." if len(overview) > 220 else ""))

                    # Phase 4 — AI explanation per movie
                    with st.spinner(f"💡 AI is reasoning about {title}..."):
                        reason = explain_movie(movie, intent)

                    if reason:
                        st.markdown(
                            f"""
                            <div class="section-card" style="margin-top:0.6rem;">
                              <span style="color:#f5e97a;font-size:0.82rem;font-weight:700;">
                                🤖 Why AI Recommended This
                              </span><br/><br/>
                              <span style="color:#d8d4c8;font-size:0.9rem;line-height:1.6;">{reason}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

# ---------------------------------------------------------------------------
# Phase 6 — Feedback / Rejection
# ---------------------------------------------------------------------------

st.divider()
st.header("👎 Reject a Movie")
st.caption("Rejected movies will be excluded from future recommendations.")

col_fb1, col_fb2 = st.columns([3, 1])
with col_fb1:
    feedback_input = st.text_input(
        "Movie title to skip",
        placeholder="e.g. Skip Train to Busan because it is related to gore",
        label_visibility="collapsed",
    )
with col_fb2:
    save_clicked = st.button("Save Feedback", use_container_width=True)

if save_clicked:
    if not feedback_input.strip():
        st.warning("Please enter a movie title or rejection statement.")
    else:
        raw = feedback_input.strip()
        if not any(raw.lower().startswith(kw) for kw in ("skip", "reject", "avoid")):
            raw = f"Skip {raw}"

        confirmation = process_feedback(raw)

        if confirmation.startswith("Could not parse"):
            st.error(confirmation)
        else:
            # Phase 3 — Task 2: Visible feedback learning
            st.success(f"✅ Memory Updated\n\n{confirmation}")

            from feedback_memory import parse_feedback
            record = parse_feedback(raw)
            if record:
                with st.spinner("🧠 Learning from your feedback..."):
                    learning = explain_feedback_learning(
                        record["movie_title"],
                        record.get("reason") or "no specific reason given",
                    )
                with st.container(border=True):
                    st.markdown("**I learned:**")
                    for line in learning.splitlines():
                        line = line.strip()
                        if line.startswith("-"):
                            st.markdown(f"- {line.lstrip('- ').strip()}")
                        elif line:
                            st.markdown(line)

# ---------------------------------------------------------------------------
# Sidebar — Phase 5: Visible Memory + What I've Learned
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## 🧠 What I've Learned About You")

    all_records = load_all_records()

    if all_records:
        with st.spinner("Summarising memory..."):
            summary = summarise_memory(all_records)

        likes = summary.get("likes") or []
        dislikes = summary.get("dislikes") or []

        if likes:
            st.markdown("**Likes:**")
            for item in likes:
                st.markdown(f"- {item}")

        if dislikes:
            st.markdown("**Dislikes:**")
            for item in dislikes:
                st.markdown(f"- {item}")

        st.divider()
        st.markdown("**Rejected Titles:**")
        rejected_titles = load_rejected_titles()
        if rejected_titles:
            for title in sorted(rejected_titles):
                st.markdown(f"- {title.title()}")
        else:
            st.caption("None yet.")

        st.divider()
        st.caption(f"📂 {len(all_records)} memory record(s) stored")

    else:
        st.caption(
            "No feedback stored yet. Reject a movie below "
            "and I'll start learning your preferences."
        )
