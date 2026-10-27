import re
from rapidfuzz import fuzz


def parse_duration_to_seconds(duration_val) -> int | None:
    """Converts a duration string (e.g. '3:45', '1:02:15') or integer to seconds."""
    if duration_val is None:
        return None
    if isinstance(duration_val, (int, float)):
        return int(duration_val)
    if isinstance(duration_val, str):
        parts = duration_val.strip().split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif parts[0].isdigit():
                return int(parts[0])
        except (ValueError, TypeError):
            return None
    return None


def clean_title(title: str) -> str:
    """Cleans track titles by removing noise, video tags, featured artist tags, and remastered tags."""
    if not title:
        return ""

    # Common tags to strip
    patterns = [
        r"\((?:feat|ft|featuring)\.?\s*[^)]+\)",  # (feat. Artist)
        r"\[(?:feat|ft|featuring)\.?\s*[^\]]+\]",  # [feat. Artist]
        r"\((?:official|lyric|video|visualizer)[^)]*\)",
        r"\[(?:official|lyric|video|visualizer)[^\]]*\]",
        r"\((?:(?:\d{4}\s*)?remastered|remaster|deluxe|bonus\s*track|live|radio\s*edit)[^)]*\)",
        r"\[(?:(?:\d{4}\s*)?remastered|remaster|deluxe|bonus\s*track|live|radio\s*edit)[^\]]*\]",
        r"-\s*(?:(?:\d{4}\s*)?remastered|(?:\d{4}\s*)?remaster|live|radio\s*edit|single\s*version).*",
    ]

    cleaned = title
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    # Remove extra spaces and special characters
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else title.strip()


def is_duration_match(dur1_sec: int | None, dur2_sec: int | None, tolerance_sec: int = 8) -> bool:
    """Returns True if both durations are within tolerance_sec of each other."""
    if dur1_sec is None or dur2_sec is None:
        # If duration cannot be determined, allow match based purely on fuzzy title/artist
        return True
    return abs(dur1_sec - dur2_sec) <= tolerance_sec


def calculate_match_score(
    title1: str,
    artist1: str,
    title2: str,
    artist2: str,
    dur1_sec: int | None = None,
    dur2_sec: int | None = None,
    tolerance_sec: int = 8,
) -> float:
    """
    Computes a match score from 0.0 to 100.0 between two tracks.
    Penalizes if duration is outside tolerance.
    """
    c_title1 = clean_title(title1).lower()
    c_title2 = clean_title(title2).lower()
    title_score = fuzz.token_set_ratio(c_title1, c_title2)

    c_art1 = clean_title(artist1).lower()
    c_art2 = clean_title(artist2).lower()
    artist_score = fuzz.token_set_ratio(c_art1, c_art2)

    # Base weighted score: 60% title, 40% artist
    total_score = (title_score * 0.6) + (artist_score * 0.4)

    # If duration mismatch, penalize heavily
    if dur1_sec is not None and dur2_sec is not None:
        diff = abs(dur1_sec - dur2_sec)
        if diff > tolerance_sec:
            total_score -= min(40.0, diff * 3)

    return max(0.0, total_score)
