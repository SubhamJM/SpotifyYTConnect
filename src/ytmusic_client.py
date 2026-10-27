import json
import logging
import os
import tempfile
from typing import Optional
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.credentials import OAuthCredentials
from src.matcher import clean_title, parse_duration_to_seconds, calculate_match_score

logger = logging.getLogger(__name__)


class YTMusicClient:
    def __init__(
        self,
        oauth_json_str: str = "",
        browser_json_str: str = "",
        client_id: str = "",
        client_secret: str = "",
    ):
        self.oauth_json_str = oauth_json_str
        self.browser_json_str = browser_json_str
        self.client_id = client_id
        self.client_secret = client_secret
        self.temp_file: Optional[str] = None
        self.is_authenticated = False
        self.yt = self._authenticate()

    def _authenticate(self) -> YTMusic:
        # 1. Try OAuth from raw JSON environment string
        if self.oauth_json_str:
            try:
                data = json.loads(self.oauth_json_str)
                cid = self.client_id or data.get("client_id")
                csec = self.client_secret or data.get("client_secret")

                # Write to temporary file for ytmusicapi to manage token cache
                with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
                    json.dump(data, f)
                    self.temp_file = f.name

                creds = OAuthCredentials(cid, csec) if cid and csec else None
                yt = YTMusic(auth=self.temp_file, oauth_credentials=creds)
                self.is_authenticated = True
                logger.info("Successfully authenticated with YouTube Music via YTM_OAUTH_JSON")
                return yt
            except Exception as e:
                logger.error(f"Failed to authenticate with YTM_OAUTH_JSON: {e}")

        # 2. Try local oauth.json file
        if os.path.isfile("oauth.json"):
            try:
                with open("oauth.json") as f:
                    data = json.load(f)
                cid = self.client_id or data.get("client_id")
                csec = self.client_secret or data.get("client_secret")
                creds = OAuthCredentials(cid, csec) if cid and csec else None

                yt = YTMusic(auth="oauth.json", oauth_credentials=creds)
                self.is_authenticated = True
                logger.info("Successfully authenticated with YouTube Music via local oauth.json")
                return yt
            except Exception as e:
                logger.error(f"Failed to authenticate with local oauth.json: {e}")

        # 3. Try Browser Headers JSON (env string or local file)
        browser_data = None
        if self.browser_json_str:
            try:
                browser_data = json.loads(self.browser_json_str)
            except Exception:
                pass
        elif os.path.isfile("browser.json"):
            try:
                with open("browser.json") as f:
                    browser_data = json.load(f)
            except Exception:
                pass

        if browser_data:
            try:
                yt = YTMusic(auth=browser_data)
                self.is_authenticated = True
                logger.info("Successfully authenticated with YouTube Music via browser headers")
                return yt
            except Exception as e:
                logger.error(f"Failed to authenticate with browser headers: {e}")

        # 4. Anonymous client (Read-only for public playlists)
        logger.warning(
            "No YouTube Music credentials provided. Running in Anonymous Read-Only mode."
        )
        return YTMusic()

    def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        """Fetches all tracks from a YouTube Music playlist."""
        tracks = []
        try:
            # limit=None fetches all continuations in ytmusicapi
            playlist_data = self.yt.get_playlist(playlistId=playlist_id, limit=None)
            raw_tracks = playlist_data.get("tracks", [])

            for item in raw_tracks:
                video_id = item.get("videoId")
                if not video_id:
                    continue

                artists = [a.get("name", "") for a in item.get("artists", []) if a.get("name")]
                artist_str = ", ".join(artists)

                # Duration can be in 'duration_seconds' or 'duration' string
                duration_sec = item.get("duration_seconds")
                if duration_sec is None:
                    duration_sec = parse_duration_to_seconds(item.get("duration"))

                album_info = item.get("album")
                album_name = album_info.get("name", "") if isinstance(album_info, dict) else ""

                tracks.append(
                    {
                        "id": video_id,
                        "title": item.get("title", ""),
                        "artists": artists,
                        "artist_str": artist_str,
                        "duration_sec": duration_sec,
                        "album": album_name,
                    }
                )

        except Exception as e:
            logger.error(f"Error fetching YouTube Music playlist '{playlist_id}': {e}")
            raise

        logger.info(f"Loaded {len(tracks)} tracks from YouTube Music playlist '{playlist_id}'")
        return tracks

    def search_track(
        self,
        title: str,
        artist: str,
        target_duration_sec: int | None = None,
        min_score: float = 65.0,
    ) -> dict | None:
        """Searches YouTube Music for the best matching track."""
        c_title = clean_title(title)
        primary_artist = artist.split(",")[0].split("&")[0].strip()

        # Try filtered 'songs' first (official studio audio)
        best_match = self._perform_search(
            query=f"{primary_artist} - {c_title}",
            filter_type="songs",
            title=title,
            artist=artist,
            target_duration_sec=target_duration_sec,
            min_score=min_score,
        )

        if best_match and best_match["score"] >= 80.0:
            return best_match

        # Fallback to 'videos' filter if no high confidence match
        fallback_match = self._perform_search(
            query=f"{primary_artist} - {c_title}",
            filter_type="videos",
            title=title,
            artist=artist,
            target_duration_sec=target_duration_sec,
            min_score=min_score,
        )

        if fallback_match:
            if not best_match or fallback_match["score"] > best_match["score"]:
                return fallback_match

        return best_match

    def _perform_search(
        self,
        query: str,
        filter_type: str,
        title: str,
        artist: str,
        target_duration_sec: int | None,
        min_score: float,
    ) -> dict | None:
        try:
            results = self.yt.search(query=query, filter=filter_type, limit=10)
        except Exception as e:
            logger.debug(f"Search failed for '{query}' with filter {filter_type}: {e}")
            return None

        best = None
        highest_score = 0.0

        for item in results:
            video_id = item.get("videoId")
            if not video_id:
                continue

            item_artists = [a.get("name", "") for a in item.get("artists", []) if a.get("name")]
            item_artist_str = ", ".join(item_artists)
            item_dur = item.get("duration_seconds")
            if item_dur is None:
                item_dur = parse_duration_to_seconds(item.get("duration"))

            score = calculate_match_score(
                title1=title,
                artist1=artist,
                title2=item.get("title", ""),
                artist2=item_artist_str,
                dur1_sec=target_duration_sec,
                dur2_sec=item_dur,
            )

            if score > highest_score and score >= min_score:
                highest_score = score
                best = {
                    "id": video_id,
                    "title": item.get("title", ""),
                    "artist": item_artist_str,
                    "duration_sec": item_dur,
                    "score": score,
                }

        return best

    def add_tracks_to_playlist(self, playlist_id: str, video_ids: list[str]) -> int:
        """Adds video IDs to the YouTube Music destination playlist."""
        if not self.is_authenticated:
            raise PermissionError(
                "Cannot modify YouTube Music playlist without authentication. "
                "Provide YTM_OAUTH_JSON secret or oauth.json file."
            )

        if not video_ids:
            return 0

        try:
            # ytmusicapi add_playlist_items adds all videoIds, duplicates=False avoids internal dupes
            response = self.yt.add_playlist_items(
                playlistId=playlist_id,
                videoIds=video_ids,
                duplicates=False,
            )
            logger.info(f"Added {len(video_ids)} tracks to YouTube Music playlist '{playlist_id}': {response}")
            return len(video_ids)
        except Exception as e:
            logger.error(f"Failed to add tracks to YouTube Music playlist '{playlist_id}': {e}")
            raise

    def __del__(self):
        # Clean up temporary oauth file if created
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except Exception:
                pass
