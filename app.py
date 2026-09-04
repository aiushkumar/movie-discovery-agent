import sys
from pathlib import Path

# Make src/movie_discovery importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "movie_discovery"))

import streamlit as st
from feedback_memory import load_rejected_titles, process_feedback
from tmdb_service import discover_movies, parse_query

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Movie Discovery AI Agent", page_icon="🎬")

# ---------------------------------------------------------------------------
# Dark cinematic background — Batman-inspired Gotham cityscape
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Full-page background image — no fixed attachment (breaks scroll in Chromium) */
    .stApp {
        background-image: url("https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1920&q=80");
        background-size: cover;
        background-position: center top;
        background-repeat: no-repeat;
        background-attachment: scroll;
    }

    /* Dark overlay using a gradient on top of the background image */
    .stApp {
        background-image:
            linear-gradient(rgba(5, 5, 15, 0.83), rgba(5, 5, 15, 0.83)),
            url("https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1920&q=80");
    }

    /* Main content area — semi-transparent dark panel */
    .block-container {
        background: rgba(10, 10, 20, 0.60) !important;
        border-radius: 12px;
        padding: 2.5rem 3rem !important;
        backdrop-filter: blur(3px);
        -webkit-backdrop-filter: blur(3px);
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: rgba(8, 8, 18, 0.92) !important;
        border-right: 1px solid rgba(255, 200, 0, 0.15);
    }

    /* Headings */
    h1, h2, h3 {
        color: #f5f0e0 !important;
        letter-spacing: 0.02em;
    }

    /* Body text */
    p, li, label, .stCaption, .stMarkdown {
        color: #d0ccc0 !important;
    }

    /* Metric labels and values */
    [data-testid="stMetricLabel"] {
        color: #b0aa99 !important;
    }
    [data-testid="stMetricValue"] {
        color: #f5e97a !important;
    }

    /* Input boxes */
    .stTextInput > div > div > input {
        background-color: rgba(20, 20, 35, 0.85) !important;
        color: #f0ece0 !important;
        border: 1px solid rgba(255, 200, 0, 0.3) !important;
        border-radius: 6px;
    }

    /* Buttons — gold accent inspired by Batman logo */
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

    /* Divider */
    hr {
        border-color: rgba(255, 200, 0, 0.2) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Page title and description
# ---------------------------------------------------------------------------

st.title("🎬 Movie Discovery AI Agent")

st.markdown(
    """
    Discover personalized movie recommendations powered by TMDB and natural language search.

    The app learns from your feedback by remembering rejected movies and automatically
    excluding them from future recommendations using its built-in memory system.
    """
)

st.divider()

# ---------------------------------------------------------------------------
# Section 1 — Recommendations
# ---------------------------------------------------------------------------

st.header("Find Movies")

query = st.text_input(
    "Which movie genre you want to watch movie from?",
    placeholder="e.g. best horror movies after 2015",
)

if st.button("Get Recommendations"):
    if not query.strip():
        st.warning("Please enter a query before searching.")
    else:
        with st.spinner("Fetching recommendations..."):
            parsed = parse_query(query)
            movies = discover_movies(parsed)

        st.subheader("Query Details")
        col1, col2, col3 = st.columns(3)
        col1.metric("Genre", parsed["genre"] or "Not detected")
        col2.metric("Year from", str(parsed["year"]) if parsed["year"] else "Any")
        col3.metric("Sort by", "Rating" if parsed["sort_by"] == "vote_average.desc" else "Popularity")

        st.subheader("Top Recommendations")

        if not movies:
            st.info("No recommendations found. Try a different query, or check that rejected movies are not filtering everything out.")
        else:
            for movie in movies:
                title = movie.get("title", "Unknown")
                release_date = movie.get("release_date", "N/A")
                rating = movie.get("vote_average", "N/A")
                overview = movie.get("overview", "")

                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    col_a, col_b = st.columns(2)
                    col_a.caption(f"📅 {release_date}")
                    col_b.caption(f"⭐ {rating}")
                    if overview:
                        st.caption(overview[:200] + ("..." if len(overview) > 200 else ""))

# ---------------------------------------------------------------------------
# Section 2 — Feedback
# ---------------------------------------------------------------------------

st.divider()
st.header("Reject a Movie")
st.caption("Rejected movies will be excluded from future recommendations.")

feedback_input = st.text_input(
    "Movie title to skip",
    placeholder="e.g. Skip Train to Busan because it is related to gore",
)

if st.button("Save Feedback"):
    if not feedback_input.strip():
        st.warning("Please enter a movie title or rejection statement.")
    else:
        # Accept plain title as well as full "Skip X because Y" syntax
        raw = feedback_input.strip()
        if not any(raw.lower().startswith(kw) for kw in ("skip", "reject", "avoid")):
            raw = f"Skip {raw}"

        confirmation = process_feedback(raw)
        if confirmation.startswith("Could not parse"):
            st.error(confirmation)
        else:
            st.success(confirmation)

# ---------------------------------------------------------------------------
# Section 3 — Current rejection memory (sidebar)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Rejection Memory")
    rejected = load_rejected_titles()
    if rejected:
        st.caption(f"{len(rejected)} movie(s) currently rejected:")
        for title in sorted(rejected):
            st.markdown(f"- {title.title()}")
    else:
        st.caption("No rejections saved yet.")
