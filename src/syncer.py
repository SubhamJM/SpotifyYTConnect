import logging
import time
from src.spotify_client import SpotifyClient
from src.ytmusic_client import YTMusicClient
from src.matcher import clean_title, calculate_match_score

logger = logging.getLogger(__name__)


def is_track_already_in_list(
    title: str,
    artist: str,
    track_list: list[dict],
    duration_sec: int | None = None,
    threshold: float = 75.0,
) -> bool:
    """Checks whether a track already exists in a given destination track list using fuzzy matching."""
    c_title = clean_title(title).lower()
    c_artist = clean_title(artist).lower()

    for item in track_list:
        item_title = clean_title(item.get("title", "")).lower()
        item_artist = clean_title(item.get("artist_str", "")).lower()

        # Exact clean match shortcut
        if c_title == item_title and (not c_artist or c_artist in item_artist or item_artist in c_artist):
            return True

        # Fuzzy match check
        score = calculate_match_score(
            title1=title,
            artist1=artist,
            title2=item.get("title", ""),
            artist2=item.get("artist_str", ""),
            dur1_sec=duration_sec,
            dur2_sec=item.get("duration_sec"),
        )
        if score >= threshold:
            return True

    return False


def sync_spotify_to_ytmusic(
    sp_client: SpotifyClient,
    yt_client: YTMusicClient,
    spotify_playlist_id: str,
    ytmusic_playlist_id: str,
) -> dict:
    """Syncs tracks from Spotify to YouTube Music."""
    logger.info("=" * 60)
    logger.info(f"Syncing: Spotify [{spotify_playlist_id}] -> YouTube Music [{ytmusic_playlist_id}]")
    logger.info("=" * 60)

    sp_tracks = sp_client.get_playlist_tracks(spotify_playlist_id)
    yt_tracks = yt_client.get_playlist_tracks(ytmusic_playlist_id)

    existing_yt_ids = {t["id"] for t in yt_tracks}
    to_add_video_ids = []
    added_titles = []
    unmatched_tracks = []

    for idx, track in enumerate(sp_tracks, 1):
        title = track["title"]
        artist = track["artist_str"]
        dur = track["duration_sec"]

        # Check if song is already present in YT Music playlist
        if is_track_already_in_list(title, artist, yt_tracks, duration_sec=dur):
            logger.debug(f"[{idx}/{len(sp_tracks)}] Already in YT Music: '{title}' by '{artist}'")
            continue

        logger.info(f"[{idx}/{len(sp_tracks)}] Searching YT Music for: '{title}' - '{artist}'...")
        match = yt_client.search_track(title=title, artist=artist, target_duration_sec=dur)

        if match:
            vid = match["id"]
            if vid not in existing_yt_ids and vid not in to_add_video_ids:
                to_add_video_ids.append(vid)
                added_titles.append(f"{title} - {artist} -> (Matched: {match['title']} [{match['score']:.1f}%])")
                # Add to local list representation to prevent duplicate matches in this run
                yt_tracks.append({"id": vid, "title": match["title"], "artist_str": match["artist"], "duration_sec": match["duration_sec"]})
                logger.info(f"  + Queued: '{match['title']}' ({match['artist']}) [Score: {match['score']:.1f}%]")
            else:
                logger.debug(f"  - Video ID {vid} already in destination playlist.")
        else:
            logger.warning(f"  x No suitable match found on YT Music for: '{title}' - '{artist}'")
            unmatched_tracks.append(f"{title} - {artist}")

        # Rate-limiting courtesy delay
        time.sleep(0.15)

    total_added = 0
    if to_add_video_ids:
        logger.info(f"Adding {len(to_add_video_ids)} new tracks to YouTube Music...")
        total_added = yt_client.add_tracks_to_playlist(ytmusic_playlist_id, to_add_video_ids)
    else:
        logger.info("YouTube Music playlist is already fully up to date!")

    return {
        "source": "Spotify",
        "target": "YouTube Music",
        "total_source_tracks": len(sp_tracks),
        "total_added": total_added,
        "added_details": added_titles,
        "unmatched": unmatched_tracks,
    }


def sync_ytmusic_to_spotify(
    yt_client: YTMusicClient,
    sp_client: SpotifyClient,
    ytmusic_playlist_id: str,
    spotify_playlist_id: str,
) -> dict:
    """Syncs tracks from YouTube Music to Spotify."""
    logger.info("=" * 60)
    logger.info(f"Syncing: YouTube Music [{ytmusic_playlist_id}] -> Spotify [{spotify_playlist_id}]")
    logger.info("=" * 60)

    yt_tracks = yt_client.get_playlist_tracks(ytmusic_playlist_id)
    sp_tracks = sp_client.get_playlist_tracks(spotify_playlist_id)

    existing_sp_uris = {t["uri"] for t in sp_tracks}
    to_add_uris = []
    added_titles = []
    unmatched_tracks = []

    for idx, track in enumerate(yt_tracks, 1):
        title = track["title"]
        artist = track["artist_str"]
        dur = track["duration_sec"]

        # Check if song is already present in Spotify playlist
        if is_track_already_in_list(title, artist, sp_tracks, duration_sec=dur):
            logger.debug(f"[{idx}/{len(yt_tracks)}] Already in Spotify: '{title}' by '{artist}'")
            continue

        logger.info(f"[{idx}/{len(yt_tracks)}] Searching Spotify for: '{title}' - '{artist}'...")
        match = sp_client.search_track(title=title, artist=artist, target_duration_sec=dur)

        if match:
            uri = match["uri"]
            if uri not in existing_sp_uris and uri not in to_add_uris:
                to_add_uris.append(uri)
                added_titles.append(f"{title} - {artist} -> (Matched: {match['title']} [{match['score']:.1f}%])")
                sp_tracks.append({"uri": uri, "title": match["title"], "artist_str": match["artist"], "duration_sec": match["duration_sec"]})
                logger.info(f"  + Queued: '{match['title']}' ({match['artist']}) [Score: {match['score']:.1f}%]")
            else:
                logger.debug(f"  - Spotify URI {uri} already in destination playlist.")
        else:
            logger.warning(f"  x No suitable match found on Spotify for: '{title}' - '{artist}'")
            unmatched_tracks.append(f"{title} - {artist}")

        time.sleep(0.15)

    total_added = 0
    if to_add_uris:
        logger.info(f"Adding {len(to_add_uris)} new tracks to Spotify...")
        total_added = sp_client.add_tracks_to_playlist(spotify_playlist_id, to_add_uris)
    else:
        logger.info("Spotify playlist is already fully up to date!")

    return {
        "source": "YouTube Music",
        "target": "Spotify",
        "total_source_tracks": len(yt_tracks),
        "total_added": total_added,
        "added_details": added_titles,
        "unmatched": unmatched_tracks,
    }
