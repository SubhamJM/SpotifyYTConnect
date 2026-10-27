import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from spotipy.cache_handler import MemoryCacheHandler
from src.matcher import clean_title, calculate_match_score

logger = logging.getLogger(__name__)


class HeadlessSpotifyOAuth(SpotifyOAuth):
    def _get_user_input(self, prompt):
        raise spotipy.SpotifyOauthError(
            "Spotify authorization required or token invalid. Headless mode does not support interactive CLI login."
        )


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.is_authenticated_user = bool(refresh_token)
        self.sp = self._authenticate()

    def _authenticate(self) -> spotipy.Spotify:
        if self.refresh_token:
            logger.info("Authenticating with Spotify using OAuth Refresh Token (Read & Write)...")
            cache_handler = MemoryCacheHandler(token_info={"refresh_token": self.refresh_token})
            oauth = HeadlessSpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri="http://127.0.0.1:9090",
                scope="playlist-modify-public playlist-modify-private playlist-read-private",
                cache_handler=cache_handler,
                open_browser=False,
            )
            return spotipy.Spotify(auth_manager=oauth)
        else:
            logger.info("Authenticating with Spotify using Client Credentials (Read-Only)...")
            client_credentials_manager = SpotifyClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            return spotipy.Spotify(auth_manager=client_credentials_manager)

    def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        """Fetches all tracks from a Spotify playlist with pagination."""
        tracks = []
        offset = 0
        limit = 100

        try:
            while True:
                results = self.sp.playlist_items(
                    playlist_id=playlist_id,
                    offset=offset,
                    limit=limit,
                    additional_types=("track",),
                )
                items = results.get("items", [])
                if not items:
                    break

                for item in items:
                    track = item.get("track")
                    if not track or not track.get("id"):
                        continue

                    artists = [a.get("name", "") for a in track.get("artists", []) if a.get("name")]
                    artist_str = ", ".join(artists)
                    duration_sec = (track.get("duration_ms") or 0) // 1000

                    tracks.append(
                        {
                            "id": track.get("id"),
                            "uri": track.get("uri"),
                            "title": track.get("name", ""),
                            "artists": artists,
                            "artist_str": artist_str,
                            "duration_sec": duration_sec,
                            "album": track.get("album", {}).get("name", ""),
                        }
                    )

                if len(items) < limit:
                    break
                offset += len(items)

        except Exception as e:
            logger.error(f"Error fetching Spotify playlist '{playlist_id}': {e}")
            raise

        logger.info(f"Loaded {len(tracks)} tracks from Spotify playlist '{playlist_id}'")
        return tracks

    def search_track(
        self,
        title: str,
        artist: str,
        target_duration_sec: int | None = None,
        min_score: float = 65.0,
    ) -> dict | None:
        """Searches Spotify for the best matching track."""
        c_title = clean_title(title)
        primary_artist = artist.split(",")[0].split("&")[0].strip()

        queries = [
            f"track:{c_title} artist:{primary_artist}",
            f"{c_title} {primary_artist}",
            c_title,
        ]

        best_match = None
        highest_score = 0.0

        for q in queries:
            try:
                res = self.sp.search(q=q, limit=10, type="track")
                items = res.get("tracks", {}).get("items", [])
                for item in items:
                    item_artists = [a.get("name", "") for a in item.get("artists", [])]
                    item_artist_str = ", ".join(item_artists)
                    item_dur = (item.get("duration_ms") or 0) // 1000

                    score = calculate_match_score(
                        title1=title,
                        artist1=artist,
                        title2=item.get("name", ""),
                        artist2=item_artist_str,
                        dur1_sec=target_duration_sec,
                        dur2_sec=item_dur,
                    )

                    if score > highest_score and score >= min_score:
                        highest_score = score
                        best_match = {
                            "id": item.get("id"),
                            "uri": item.get("uri"),
                            "title": item.get("name"),
                            "artist": item_artist_str,
                            "duration_sec": item_dur,
                            "score": score,
                        }

                if highest_score >= 85.0:
                    break  # High confidence match found

            except Exception as e:
                logger.debug(f"Search query failed '{q}': {e}")

        return best_match

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list[str]) -> int:
        """Adds tracks to the destination Spotify playlist in chunks of 100."""
        if not self.is_authenticated_user:
            raise PermissionError(
                "Cannot modify Spotify playlist without SPOTIFY_REFRESH_TOKEN. "
                "Run `python setup_spotify.py` to authorize your account."
            )

        if not track_uris:
            return 0

        total_added = 0
        chunk_size = 100

        for i in range(0, len(track_uris), chunk_size):
            chunk = track_uris[i : i + chunk_size]
            try:
                self.sp.playlist_add_items(playlist_id=playlist_id, items=chunk)
                total_added += len(chunk)
                logger.info(f"Added {len(chunk)} tracks to Spotify playlist '{playlist_id}'")
            except Exception as e:
                logger.error(f"Failed to add tracks chunk to Spotify playlist '{playlist_id}': {e}")
                raise

        return total_added

    def get_user_playlists(self, limit: int = 50) -> list[dict]:
        """Fetches playlists from the authenticated Spotify user account."""
        if not self.is_authenticated_user:
            return []
        try:
            results = self.sp.current_user_playlists(limit=limit)
            playlists = []
            for item in results.get("items", []):
                if not item:
                    continue
                images = item.get("images", [])
                image_url = images[0]["url"] if images else ""
                playlists.append(
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "tracks_count": item.get("tracks", {}).get("total", 0),
                        "image_url": image_url,
                        "url": item.get("external_urls", {}).get("spotify", ""),
                    }
                )
            return playlists
        except Exception as e:
            logger.error(f"Failed to fetch user Spotify playlists: {e}")
            return []

    def get_playlist_details(self, playlist_id: str) -> dict:
        """Fetches metadata for a single playlist."""
        try:
            res = self.sp.playlist(playlist_id=playlist_id, fields="id,name,description,images,tracks.total")
            images = res.get("images", [])
            return {
                "id": res.get("id"),
                "name": res.get("name"),
                "description": res.get("description", ""),
                "tracks_count": res.get("tracks", {}).get("total", 0),
                "image_url": images[0]["url"] if images else "",
            }
        except Exception as e:
            logger.error(f"Failed to get details for Spotify playlist '{playlist_id}': {e}")
            return {"id": playlist_id, "name": f"Spotify Playlist {playlist_id}", "tracks_count": 0}

    def create_playlist(self, name: str, description: str = "Synced by SpotifyYTConnect", public: bool = False) -> str:
        """Creates a new playlist in the user's Spotify library and returns its ID."""
        if not self.is_authenticated_user:
            raise PermissionError("Cannot create Spotify playlist without SPOTIFY_REFRESH_TOKEN.")
        try:
            user_info = self.sp.current_user()
            user_id = user_info["id"]
            new_pl = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description,
            )
            logger.info(f"Created new Spotify playlist '{name}' with ID '{new_pl['id']}'")
            return new_pl["id"]
        except Exception as e:
            logger.error(f"Failed to create Spotify playlist '{name}': {e}")
            raise
