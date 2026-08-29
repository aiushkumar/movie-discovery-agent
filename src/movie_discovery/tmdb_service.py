import os

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


load_dotenv()

READ_ACCESS_TOKEN = os.getenv("TMDB_READ_ACCESS_TOKEN")
BASE_URL = "https://api.themoviedb.org/3"


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
    query = "horror movies after 2015"

    genre = "horror"
    year = 2015

    print("\n=== Query Parsing Test ===\n")
    print("Query :", query)
    print("Genre :", genre)
    print("Year  :", year)


if __name__ == "__main__":
    print("=== TMDB Discovery Test ===\n")

    test_discover_horror_movies()

    test_parse_query()