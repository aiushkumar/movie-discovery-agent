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


if __name__ == "__main__":
    print("=== TMDB Movie Search Test ===\n")
    test_search_movie()