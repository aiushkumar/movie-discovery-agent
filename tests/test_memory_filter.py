import sys
from pathlib import Path

# Make src/movie_discovery importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "movie_discovery"))

from feedback_memory import filter_movies, load_rejected_titles

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_RECOMMENDATIONS = [
    {"title": "Train to Busan", "release_date": "2016-07-20", "vote_average": 7.6},
    {"title": "Hereditary",     "release_date": "2018-06-08", "vote_average": 7.3},
    {"title": "The Witch",      "release_date": "2015-02-27", "vote_average": 6.9},
]

REJECTED_MOVIE = "Train to Busan"

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_memory_filter():
    # 1. Load rejected titles from memory.json
    rejected_titles = load_rejected_titles()

    # 2. Print section: Rejected Movies
    print("Rejected Movies:")
    if rejected_titles:
        for title in sorted(rejected_titles):
            print(f"  - {title.title()}")
    else:
        print("  (none)")

    # 3. Print section: Original Recommendations
    print("\nOriginal Recommendations:")
    for movie in MOCK_RECOMMENDATIONS:
        print(f"  - {movie['title']}")

    # 4. Run filtering logic (suppressing its internal debug output)
    print()
    filtered = filter_movies(MOCK_RECOMMENDATIONS, rejected_titles)

    # 5. Print section: Filtered Recommendations
    print("\nFiltered Recommendations:")
    if filtered:
        for movie in filtered:
            print(f"  - {movie['title']}")
    else:
        print("  (no movies remaining)")

    # 6. Assertion: rejected movie must not appear in filtered results
    filtered_titles = [m["title"] for m in filtered]
    passed = REJECTED_MOVIE not in filtered_titles

    print()
    if passed:
        print(f"PASS  '{REJECTED_MOVIE}' was correctly removed from recommendations.")
    else:
        print(f"FAIL  '{REJECTED_MOVIE}' still appears in recommendations.")

    return passed


if __name__ == "__main__":
    print("=== Memory Filter Test ===\n")
    result = test_memory_filter()
    sys.exit(0 if result else 1)
