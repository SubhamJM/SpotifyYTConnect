import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()


def extract_spotify_playlist_id(url_or_id: str) -> str:
    """Extracts the clean Spotify playlist ID from a URI, full URL, or plain ID."""
    if not url_or_id:
        return ""
    url_or_id = url_or_id.strip()

    # Match spotify:playlist:ID
    uri_match = re.search(r"spotify:playlist:([a-zA-Z0-9]+)", url_or_id)
    if uri_match:
        return uri_match.group(1)

    # Match https://open.spotify.com/playlist/ID
    url_match = re.search(r"open\.spotify\.com/playlist/([a-zA-Z0-9]+)", url_or_id)
    if url_match:
        return url_match.group(1)

    # Default to raw ID without query params
    return url_or_id.split("?")[0].strip()


def extract_ytmusic_playlist_id(url_or_id: str) -> str:
    """Extracts the clean YouTube Music playlist ID from a URL or plain ID."""
    if not url_or_id:
        return ""
    url_or_id = url_or_id.strip()

    # Match ?list=ID or &list=ID
    list_match = re.search(r"[?&]list=([a-zA-Z0-9_-]+)", url_or_id)
    if list_match:
        return list_match.group(1)

    return url_or_id.split("&")[0].split("?")[0].strip()


@dataclass
class SyncPair:
    spotify_playlist_id: str
    ytmusic_playlist_id: str
    direction: str  # "spotify_to_yt", "yt_to_spotify", or "both"


class Config:
    def __init__(self):
        # Spotify credentials
        self.spotify_client_id = os.getenv("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID") or ""
        self.spotify_client_secret = os.getenv("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIFY_CLIENT_SECRET") or ""
        self.spotify_refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN") or ""

        # YouTube Music credentials
        self.ytm_oauth_json = os.getenv("YTM_OAUTH_JSON") or ""
        self.ytm_browser_json = os.getenv("YTM_BROWSER_JSON") or ""
        self.ytm_client_id = os.getenv("YTM_CLIENT_ID") or ""
        self.ytm_client_secret = os.getenv("YTM_CLIENT_SECRET") or ""

        # Sync settings
        self.sync_pairs: List[SyncPair] = self._load_sync_pairs()

    def _load_sync_pairs(self) -> List[SyncPair]:
        pairs = []
        raw_pairs_json = os.getenv("SYNC_PAIRS")
        if raw_pairs_json:
            try:
                parsed = json.loads(raw_pairs_json)
                for item in parsed:
                    sp_id = extract_spotify_playlist_id(item.get("spotify_id") or item.get("spotify_playlist_id", ""))
                    yt_id = extract_ytmusic_playlist_id(item.get("yt_id") or item.get("ytmusic_playlist_id", ""))
                    direction = (item.get("direction") or "both").lower()
                    if sp_id and yt_id:
                        pairs.append(SyncPair(sp_id, yt_id, direction))
            except Exception as e:
                print(f"[Config Warning] Failed to parse SYNC_PAIRS JSON: {e}")

        # Check sync_pairs.json file
        if not pairs and os.path.isfile("sync_pairs.json"):
            try:
                with open("sync_pairs.json", "r") as f:
                    stored = json.load(f)
                for item in stored:
                    src_plat = item.get("source_platform", "spotify")
                    src_id = item.get("source_id", "")
                    tgt_id = item.get("target_id", "auto")
                    if src_plat == "spotify":
                        pairs.append(SyncPair(src_id, tgt_id, "spotify_to_yt"))
                    else:
                        pairs.append(SyncPair(tgt_id, src_id, "yt_to_spotify"))
            except Exception as e:
                print(f"[Config Warning] Failed to parse sync_pairs.json: {e}")

        # Fallback to single pair env vars if no valid pairs were added
        if not pairs:
            sp_id = extract_spotify_playlist_id(os.getenv("SPOTIFY_PLAYLIST_ID", ""))
            yt_id = extract_ytmusic_playlist_id(os.getenv("YTMUSIC_PLAYLIST_ID", ""))
            direction = (os.getenv("SYNC_DIRECTION") or "both").lower()
            if sp_id and yt_id:
                pairs.append(SyncPair(sp_id, yt_id, direction))

        return pairs

    def validate(self) -> List[str]:
        """Returns a list of missing configuration warnings or errors."""
        errors = []
        if not self.spotify_client_id:
            errors.append("SPOTIPY_CLIENT_ID is not set.")
        if not self.spotify_client_secret:
            errors.append("SPOTIPY_CLIENT_SECRET is not set.")

        has_local_auth = (
            os.path.isfile("oauth.json")
            or os.path.isfile("browser.json")
            or bool(self.ytm_oauth_json)
            or bool(self.ytm_browser_json)
        )
        if not has_local_auth:
            errors.append(
                "YouTube Music authentication is missing. Provide YTM_BROWSER_JSON, YTM_OAUTH_JSON, browser.json, or oauth.json."
            )

        if not self.sync_pairs:
            errors.append("No playlist sync pairs configured. Set SPOTIFY_PLAYLIST_ID and YTMUSIC_PLAYLIST_ID.")

        return errors
