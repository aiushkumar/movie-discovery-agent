import os
import re

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from feedback_memory import filter_movies, load_rejected_titles


load_dotenv(override=False)  # No-op on Hugging Face Spaces where env vars come from Secrets

READ_ACCESS_TOKEN = os.getenv("TMDB_READ_ACCESS_TOKEN")
BASE_URL = "https://api.themoviedb.org/3"


GENRE_MAP = {
    "horror": 27,
    "action": 28,
    "comedy": 35,
    "drama": 18,
    "thriller": 53,
    "romance": 10749,
    "science fiction": 878,
    "animation": 16,
    "documentary": 99,
    "fantasy": 14,
    "mystery": 9648,
    "adventure": 12,
    "family": 10751,
    "crime": 80,
    "history": 36,
    "music": 10402,
    "war": 10752,
    "western": 37,
}

# Keywords that indicate the user wants highest-rated results
RATING_KEYWORDS = {"best", "top", "highest rated"}


def parse_query(query: str) -> dict:
    """
    Parse a natural language movie query to extract genre, release year,
    and sort preference.

    Args:
        query: Natural language string e.g. "best horror movies after 2015"

    Returns:
        dict with keys: genre (str|None), genre_id (int|None),
                        year (int|None), sort_by (str)
    """
    query_lower = query.lower()

    # Extract genre — check multi-word genres first to avoid partial matches
    matched_genre = None
    matched_genre_id = None
    for genre, genre_id in sorted(GENRE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if genre in query_lower:
            matched_genre = genre
            matched_genre_id = genre_id
            break

    # Extract year using regex (4-digit number between 1900 and 2099)
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", query)
    year = int(year_match.group(1)) if year_match else None

    # Detect sort preference — multi-word keywords checked before single-word
    sort_by = "popularity.desc"
    for keyword in sorted(RATING_KEYWORDS, key=len, reverse=True):
        if keyword in query_lower:
            sort_by = "vote_average.desc"
            break

    return {
        "genre": matched_genre,
        "genre_id": matched_genre_id,
        "year": year,
        "sort_by": sort_by,
    }


def create_session():
    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.mount("https://", adapter)

    return session


def test_search_movie(query="Interstellar"):
    headers = {
        "Authorization": f"Bearer {READ_ACCESS_TOKEN}",
        "accept": "application/json",
    }

    url = f"{BASE_URL}/search/movie"
    session = create_session()

    response = session.get(
        url,
        headers=headers,
        params={"query": query},
        timeout=30,
    )

    print(f"Status code: {response.status_code}")

    if response.status_code != 200:
        print(response.text)
        return

    data = response.json()

    print(f"\nSearch results for '{query}':\n")

    for movie in data.get("results", [])[:5]:
        title = movie.get("title", "Unknown")
        release_date = movie.get("release_date", "N/A")

        print(f"{title} ({release_date})")


def test_discover_horror_movies():
    headers = {
        "Authorization": f"Bearer {READ_ACCESS_TOKEN}",
        "accept": "application/json",
    }

    url = f"{BASE_URL}/discover/movie"

    params = {
        "with_genres": 27,  # Horror
        "primary_release_date.gte": "2015-01-01",
        "sort_by": "vote_average.desc",
        "vote_count.gte": 500,
    }

    session = create_session()

    response = session.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    print(f"Status code: {response.status_code}")

    if response.status_code != 200:
        print(response.text)
        return

    data = response.json()

    print("\nTop Horror Movies After 2015:\n")

    for movie in data.get("results", [])[:5]:
        title = movie.get("title", "Unknown")
        release_date = movie.get("release_date", "N/A")
        rating = movie.get("vote_average", "N/A")

        print(f"{title} ({release_date}) - Rating: {rating}")


def test_parse_query():
    test_queries = [
        "best horror movies after 2015",
        "action movies after 2020",
        "comedy movies",
        "science fiction movies after 2018",
        # original test cases
        "horror movies after 2015",
        "comedy movies after 2010",
        "action movies after 2020",
    ]

    print("\n=== Query Parsing Test ===\n")
    for query in test_queries:
        result = parse_query(query)
        print(f"Query    : {query}")
        print(f"Genre    : {result['genre']}")
        print(f"Genre ID : {result['genre_id']}")
        print(f"Year     : {result['year']}")
        print(f"Sort By  : {result['sort_by']}")
        print()


def discover_movies(parsed_query: dict, limit: int = 5) -> list:
    """
    Call TMDB discover/movie endpoint using a parsed query dict.

    Accepts both legacy parse_query() output and richer Gemini intent dicts.
    Gemini intent keys (genres, year, sort_by, language) take precedence when present.

    Args:
        parsed_query: dict from parse_query() or gemini_service.parse_intent()
        limit:        Maximum number of results to return (default 5)

    Returns:
        List of up to `limit` movie dicts from TMDB, filtered against memory.
    """
    headers = {
        "Authorization": f"Bearer {READ_ACCESS_TOKEN}",
        "accept": "application/json",
    }

    params = {
        "sort_by": parsed_query.get("sort_by", "popularity.desc"),
        "vote_count.gte": 100,
    }

    # --- Genre resolution ---
    # Gemini returns "genres" (list); legacy parse_query returns "genre_id" (int)
    genre_id = parsed_query.get("genre_id")

    if not genre_id:
        gemini_genres = parsed_query.get("genres") or []
        for g in gemini_genres:
            resolved = GENRE_MAP.get(g.lower().strip())
            if resolved:
                genre_id = resolved
                break

    if genre_id:
        params["with_genres"] = genre_id

    # --- Year resolution ---
    year = parsed_query.get("year")
    if year:
        params["primary_release_date.gte"] = f"{int(year)}-01-01"

    # --- Language resolution (Gemini only) ---
    language = parsed_query.get("language")
    if language:
        # TMDB uses ISO 639-1 codes; map common names
        lang_map = {
            "korean": "ko", "english": "en", "french": "fr",
            "spanish": "es", "japanese": "ja", "hindi": "hi",
            "german": "de", "italian": "it", "portuguese": "pt",
        }
        lang_code = lang_map.get(language.lower())
        if lang_code:
            params["with_original_language"] = lang_code

    url = f"{BASE_URL}/discover/movie"
    session = create_session()

    response = session.get(url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        print(f"TMDB request failed. Status: {response.status_code}")
        print(response.text)
        return []

    results = response.json().get("results", [])[:limit + 5]  # fetch extra buffer for filtering

    # Filter out any movies the user has previously rejected
    rejected_titles = load_rejected_titles()
    results = filter_movies(results, rejected_titles)

    return results[:limit]


def recommend_movies(query: str) -> None:
    """
    End-to-end recommendation workflow:
        query -> parse_query -> discover_movies -> print recommendations.

    Args:
        query: Natural language string e.g. "horror movies after 2015"
    """
    parsed = parse_query(query)

    print(f"Original Query  : {query}")
    print(f"Detected Genre  : {parsed['genre'] or 'Not detected'}")
    print(f"Detected Year   : {parsed['year'] or 'Not detected'}")

    movies = discover_movies(parsed)

    print("\nTop Recommendations:\n")

    if not movies:
        print("No recommendations found.")
        return

    for movie in movies:
        title = movie.get("title", "Unknown")
        release_date = movie.get("release_date", "N/A")
        rating = movie.get("vote_average", "N/A")
        print(f"  Title        : {title}")
        print(f"  Release Date : {release_date}")
        print(f"  Rating       : {rating}")
        print()


if __name__ == "__main__":
    print("=== TMDB Discovery Test ===\n")

    test_discover_horror_movies()

    test_parse_query()

    print("\n=== End-to-End Recommendation ===\n")

    recommend_movies("horror movies after 2015")