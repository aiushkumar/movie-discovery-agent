import json
import os
import re
from pathlib import Path

# Resolve memory file relative to the workspace root, not the source file.
# On Hugging Face Spaces the app runs from the repo root, so this stays portable.
_REPO_ROOT = Path(os.environ.get("APP_ROOT", Path(__file__).resolve().parents[2]))
MEMORY_FILE = _REPO_ROOT / "memory.json"


# Keywords that signal a skip/rejection intent
SKIP_KEYWORDS = {"skip", "reject", "don't recommend", "not interested in", "avoid"}

# Connector words that separate the movie title from the reason
REASON_CONNECTORS = ["because", "since", "as it is", "as it's", "due to"]


def parse_feedback(user_input: str) -> dict | None:
    """
    Parse a natural language rejection statement into a structured feedback record.

    Supported pattern:
        "Skip <Movie Title> because <reason>"

    Args:
        user_input: Raw string from the user.

    Returns:
        dict with keys: action, movie_title, movie_id, reason
        None if the input is not recognised as a rejection.
    """
    text = user_input.strip()
    text_lower = text.lower()

    # Detect skip/rejection intent
    action = None
    matched_keyword = None
    for keyword in sorted(SKIP_KEYWORDS, key=len, reverse=True):
        if text_lower.startswith(keyword):
            action = "skip"
            matched_keyword = keyword
            break

    if action is None:
        return None

    # Remove the leading skip keyword to isolate the rest of the statement
    remainder = text[len(matched_keyword):].strip()

    # Split on reason connector to get title and reason
    reason = None
    movie_title = remainder

    for connector in sorted(REASON_CONNECTORS, key=len, reverse=True):
        pattern = re.compile(re.escape(connector), re.IGNORECASE)
        parts = pattern.split(remainder, maxsplit=1)
        if len(parts) == 2:
            movie_title = parts[0].strip()
            reason = parts[1].strip()
            break

    # Clean up punctuation from title
    movie_title = movie_title.strip(" .,;:")

    return {
        "action": action,
        "movie_title": movie_title,
        "movie_id": None,
        "reason": reason,
    }


def save_feedback(record: dict) -> None:
    """
    Append a feedback record to memory.json.
    Creates the file if it does not exist; appends to the list if it does.

    Args:
        record: A feedback dict produced by parse_feedback().
    """
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []

    records.append(record)

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def process_feedback(user_input: str) -> str:
    """
    Full feedback workflow:
        user_input -> parse_feedback -> save_feedback -> confirmation message.

    Args:
        user_input: Raw string from the user.

    Returns:
        Confirmation string to display to the user.
    """
    record = parse_feedback(user_input)

    if record is None:
        return "Could not parse feedback. Try: 'Skip <Movie Title> because <reason>'"

    save_feedback(record)

    lines = [
        f"Recorded: {record['movie_title']}",
        f"Reason: {record['reason'] or 'No reason provided'}",
    ]
    return "\n".join(lines)


def load_all_records() -> list:
    """
    Load the full memory.json contents for display and LLM summarisation.

    Returns:
        List of all memory dicts. Empty list if file is absent or corrupt.
    """
    if not MEMORY_FILE.exists():
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def load_rejected_titles() -> set:
    """
    Load all rejected movie titles from memory.json.

    Returns:
        A set of lowercased movie titles marked as 'skip' in memory.
        Returns an empty set if memory.json does not exist, is empty,
        or contains invalid JSON.
    """
    if not MEMORY_FILE.exists():
        return set()

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
    except (json.JSONDecodeError, OSError):
        return set()

    return {
        record["movie_title"].lower()
        for record in records
        if record.get("action") == "skip" and record.get("movie_title")
    }


def filter_movies(movies: list, rejected_titles: set) -> list:
    """
    Remove any movies whose title appears in the rejected titles set.

    Prints debug output showing what was loaded, filtered, and remaining.

    Args:
        movies:          List of TMDB movie dicts.
        rejected_titles: Set of lowercased rejected movie titles.

    Returns:
        Filtered list with rejected movies removed.
    """
    print("Rejected movies loaded:")
    if rejected_titles:
        for title in sorted(rejected_titles):
            print(f"  - {title.title()}")
    else:
        print("  (none)")

    filtered_out = []
    kept = []

    for movie in movies:
        title = movie.get("title", "")
        if title.lower() in rejected_titles:
            filtered_out.append(title)
        else:
            kept.append(movie)

    print("\nFiltered out:")
    if filtered_out:
        for title in filtered_out:
            print(f"  - {title}")
    else:
        print("  (nothing removed)")

    print("\nRemaining recommendations:")
    if kept:
        for movie in kept:
            print(f"  - {movie.get('title', 'Unknown')}")
    else:
        print("  (no recommendations left)")

    return kept


if __name__ == "__main__":
    test_inputs = [
        "Skip Train to Busan because it is related to gore",
        "Skip Midsommar because it is too disturbing",
        "Reject The Nun because bad reviews",
    ]

    print("=== Feedback Memory MVP ===\n")

    for user_input in test_inputs:
        print(f"Input : {user_input}")
        result = process_feedback(user_input)
        print(result)
        print()

    print(f"Memory written to: {MEMORY_FILE}")
