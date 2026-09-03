---
title: Movie Discovery Agent
emoji: 🎬
colorFrom: gray
colorTo: yellow
sdk: streamlit
sdk_version: 1.45.1
app_file: app.py
pinned: false
---

# Movie Discovery Agent

Discover personalized movie recommendations powered by TMDB and natural language search.

The app learns from your feedback by remembering rejected movies and automatically excluding them from future recommendations using its built-in memory system.

## Features

- Natural language movie search (e.g. "best horror movies after 2015")
- Genre and year detection
- Smart sorting — detects "best / top / highest rated" keywords
- Rejection memory — rejected movies are saved to `memory.json` and filtered from future results
- Dark cinematic UI

## Running Locally

```bash
# 1. Clone the repo and enter the project folder
cd movie-discovery-agent

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate        # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your TMDB credentials

# 5. Run the app
streamlit run app.py
```

## Environment Variables

| Variable | Description |
|---|---|
| `TMDB_READ_ACCESS_TOKEN` | TMDB API Read Access Token (JWT) |
| `TMDB_API_KEY` | TMDB API Key |

On Hugging Face Spaces, add these under **Settings → Repository Secrets**.

## Project Structure

```
movie-discovery-agent/
├── app.py                        # Streamlit UI
├── requirements.txt
├── memory.json                   # Persistent rejection memory
├── .env.example
└── src/
    └── movie_discovery/
        ├── __init__.py
        ├── tmdb_service.py       # TMDB API + recommendation logic
        └── feedback_memory.py    # Memory read/write/filter logic
```
