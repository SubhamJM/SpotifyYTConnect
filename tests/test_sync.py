import pytest
from src.matcher import clean_title, parse_duration_to_seconds, calculate_match_score, is_duration_match
from src.config import extract_spotify_playlist_id, extract_ytmusic_playlist_id


def test_clean_title():
    assert clean_title("Starboy (feat. Daft Punk)") == "Starboy"
    assert clean_title("Blinding Lights [Official Music Video]") == "Blinding Lights"
    assert clean_title("Bohemian Rhapsody - 2011 Remaster") == "Bohemian Rhapsody"
    assert clean_title("Hotel California (Live On MTV, 1994)") == "Hotel California"
    assert clean_title("Shape of You [Official Lyric Video]") == "Shape of You"


def test_parse_duration():
    assert parse_duration_to_seconds("3:45") == 225
    assert parse_duration_to_seconds("0:30") == 30
    assert parse_duration_to_seconds("1:02:15") == 3735
    assert parse_duration_to_seconds(180) == 180
    assert parse_duration_to_seconds(None) is None


def test_duration_match():
    assert is_duration_match(200, 205, tolerance_sec=8) is True
    assert is_duration_match(200, 215, tolerance_sec=8) is False
    assert is_duration_match(None, 200) is True


def test_match_score():
    score = calculate_match_score(
        title1="As It Was",
        artist1="Harry Styles",
        title2="As It Was (Official Video)",
        artist2="Harry Styles",
        dur1_sec=167,
        dur2_sec=168,
    )
    assert score >= 90.0

    # Mismatched duration should heavily penalize score
    mismatch_score = calculate_match_score(
        title1="As It Was",
        artist1="Harry Styles",
        title2="As It Was (10 Hour Loop)",
        artist2="Harry Styles",
        dur1_sec=167,
        dur2_sec=36000,
    )
    assert mismatch_score < score


def test_extract_spotify_id():
    url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=12345"
    assert extract_spotify_playlist_id(url) == "37i9dQZF1DXcBWIGoYBM5M"

    uri = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
    assert extract_spotify_playlist_id(uri) == "37i9dQZF1DXcBWIGoYBM5M"

    raw = "37i9dQZF1DXcBWIGoYBM5M"
    assert extract_spotify_playlist_id(raw) == "37i9dQZF1DXcBWIGoYBM5M"


def test_extract_ytmusic_id():
    url = "https://music.youtube.com/playlist?list=PL4fGSIFgk54Vxyz123&si=abcd"
    assert extract_ytmusic_playlist_id(url) == "PL4fGSIFgk54Vxyz123"

    yt_url = "https://www.youtube.com/playlist?list=PL4fGSIFgk54Vxyz123"
    assert extract_ytmusic_playlist_id(yt_url) == "PL4fGSIFgk54Vxyz123"

    raw = "PL4fGSIFgk54Vxyz123"
    assert extract_ytmusic_playlist_id(raw) == "PL4fGSIFgk54Vxyz123"
