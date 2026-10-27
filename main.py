import logging
import sys
from src.config import Config
from src.spotify_client import SpotifyClient
from src.ytmusic_client import YTMusicClient
from src.syncer import sync_spotify_to_ytmusic, sync_ytmusic_to_spotify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SpotifyYTConnect")


def main():
    logger.info("Initializing Spotify <-> YouTube Music Playlist Sync...")

    config = Config()
    errors = config.validate()
    if errors:
        logger.error("Configuration validation failed:")
        for err in errors:
            logger.error(f"  - {err}")
        logger.error("Please configure the required environment variables or secrets.")
        sys.exit(1)

    logger.info(f"Loaded {len(config.sync_pairs)} playlist pair(s) to synchronize.")

    # Initialize Clients
    try:
        sp_client = SpotifyClient(
            client_id=config.spotify_client_id,
            client_secret=config.spotify_client_secret,
            refresh_token=config.spotify_refresh_token,
        )
    except Exception as e:
        logger.critical(f"Failed to initialize Spotify client: {e}")
        sys.exit(1)

    try:
        yt_client = YTMusicClient(
            oauth_json_str=config.ytm_oauth_json,
            browser_json_str=config.ytm_browser_json,
            client_id=config.ytm_client_id,
            client_secret=config.ytm_client_secret,
        )
    except Exception as e:
        logger.critical(f"Failed to initialize YouTube Music client: {e}")
        sys.exit(1)

    overall_results = []

    # Execute Sync for each pair
    for i, pair in enumerate(config.sync_pairs, 1):
        logger.info(f"\n--- Processing Playlist Pair #{i} ---")
        direction = pair.direction

        # Spotify -> YouTube Music
        if direction in ("spotify_to_yt", "both"):
            try:
                res = sync_spotify_to_ytmusic(
                    sp_client=sp_client,
                    yt_client=yt_client,
                    spotify_playlist_id=pair.spotify_playlist_id,
                    ytmusic_playlist_id=pair.ytmusic_playlist_id,
                )
                overall_results.append(res)
            except Exception as e:
                logger.error(f"Error during Spotify -> YouTube Music sync: {e}")

        # YouTube Music -> Spotify
        if direction in ("yt_to_spotify", "both"):
            try:
                res = sync_ytmusic_to_spotify(
                    yt_client=yt_client,
                    sp_client=sp_client,
                    ytmusic_playlist_id=pair.ytmusic_playlist_id,
                    spotify_playlist_id=pair.spotify_playlist_id,
                )
                overall_results.append(res)
            except Exception as e:
                logger.error(f"Error during YouTube Music -> Spotify sync: {e}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SYNC SUMMARY REPORT")
    logger.info("=" * 60)
    for res in overall_results:
        logger.info(
            f"• {res['source']} -> {res['target']}: "
            f"{res['total_added']} songs added (out of {res['total_source_tracks']} total tracks)"
        )
        if res["unmatched"]:
            logger.warning(f"  Unmatched ({len(res['unmatched'])}): {', '.join(res['unmatched'][:5])}")
            if len(res["unmatched"]) > 5:
                logger.warning(f"  ...and {len(res['unmatched']) - 5} more.")

    logger.info("\nAll sync tasks finished successfully.")


if __name__ == "__main__":
    main()
