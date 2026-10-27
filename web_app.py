import json
import logging
import os
import threading
import time
import urllib.parse
import requests
from flask import Flask, render_template, request, jsonify, redirect, session
from dotenv import set_key, load_dotenv

from src.config import Config, extract_spotify_playlist_id, extract_ytmusic_playlist_id
from src.spotify_client import SpotifyClient
from src.ytmusic_client import YTMusicClient
from src.syncer import sync_spotify_to_ytmusic, sync_ytmusic_to_spotify
from setup_ytmusic import extract_browser_auth

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "spotifyytconnect-secret-key-123")


def get_redirect_uri():
    proto = request.headers.get("X-Forwarded-Proto", "http")
    if "onrender.com" in request.host or "https://" in request.url_root:
        proto = "https"
    return f"{proto}://{request.host}/callback"

# In-memory status & logs for the background sync job
sync_state = {
    "is_running": False,
    "current_task": "",
    "logs": [],
    "last_result": None,
    "completed_at": None,
}


class LogCaptureHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        sync_state["logs"].append(msg)
        if len(sync_state["logs"]) > 200:
            sync_state["logs"].pop(0)


# Attach custom log handler to capture logs for the web UI
log_capture = LogCaptureHandler()
log_capture.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(log_capture)
logging.getLogger().setLevel(logging.INFO)


def load_pairs_from_storage() -> list[dict]:
    """Loads pairs from sync_pairs.json or falls back to env vars."""
    if os.path.isfile("sync_pairs.json"):
        try:
            with open("sync_pairs.json", "r") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to Config
    cfg = Config()
    pairs = []
    for p in cfg.sync_pairs:
        pairs.append(
            {
                "source_platform": "spotify" if p.direction in ("spotify_to_yt", "both") else "ytmusic",
                "source_id": p.spotify_playlist_id if p.direction in ("spotify_to_yt", "both") else p.ytmusic_playlist_id,
                "target_platform": "ytmusic" if p.direction in ("spotify_to_yt", "both") else "spotify",
                "target_id": p.ytmusic_playlist_id if p.direction in ("spotify_to_yt", "both") else p.spotify_playlist_id,
                "name": "Sync Pair",
            }
        )
    return pairs


def save_pairs_to_storage(pairs: list[dict]):
    with open("sync_pairs.json", "w") as f:
        json.dump(pairs, f, indent=2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    cfg = Config()
    spotify_connected = False
    spotify_user = None
    if cfg.spotify_client_id and cfg.spotify_client_secret:
        try:
            sp = SpotifyClient(cfg.spotify_client_id, cfg.spotify_client_secret, cfg.spotify_refresh_token)
            if sp.is_authenticated_user:
                user_info = sp.sp.current_user()
                spotify_connected = True
                spotify_user = user_info.get("display_name") or user_info.get("id")
            else:
                spotify_connected = True
                spotify_user = "Read-Only (Client Credentials)"
        except Exception:
            spotify_connected = False

    yt_connected = False
    try:
        yt = YTMusicClient(cfg.ytm_oauth_json, cfg.ytm_browser_json, cfg.ytm_client_id, cfg.ytm_client_secret)
        yt_connected = yt.is_authenticated
    except Exception:
        yt_connected = False

    pairs = load_pairs_from_storage()

    return jsonify(
        {
            "spotify": {
                "connected": spotify_connected,
                "user": spotify_user,
                "has_refresh_token": bool(cfg.spotify_refresh_token),
            },
            "ytmusic": {
                "connected": yt_connected,
            },
            "pairs_count": len(pairs),
            "is_syncing": sync_state["is_running"],
        }
    )


@app.route("/api/connect/spotify/auth-url", methods=["POST"])
def get_spotify_auth_url():
    data = request.json or {}
    client_id = data.get("client_id", "").strip()
    client_secret = data.get("client_secret", "").strip()

    if not client_id or not client_secret:
        return jsonify({"success": False, "error": "Client ID and Client Secret are required."}), 400

    session["spotify_client_id"] = client_id
    session["spotify_client_secret"] = client_secret
    set_key(".env", "SPOTIPY_CLIENT_ID", client_id)
    set_key(".env", "SPOTIPY_CLIENT_SECRET", client_secret)

    redirect_uri = get_redirect_uri()
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "playlist-modify-public playlist-modify-private playlist-read-private",
        "show_dialog": "true",
    }
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
    return jsonify({"success": True, "auth_url": auth_url, "redirect_uri": redirect_uri})


@app.route("/callback")
def spotify_callback():
    code = request.args.get("code")
    err = request.args.get("error")
    if err:
        return f"Spotify authorization error: {err}. <br><a href='/'>Return to Dashboard</a>", 400

    if not code:
        return "Missing authorization code from Spotify. <br><a href='/'>Return to Dashboard</a>", 400

    cfg = Config()
    client_id = session.get("spotify_client_id") or cfg.spotify_client_id
    client_secret = session.get("spotify_client_secret") or cfg.spotify_client_secret
    redirect_uri = get_redirect_uri()

    try:
        res = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        data = res.json()
        if "error" in data:
            desc = data.get("error_description", data.get("error"))
            return f"Spotify Token Exchange Error: {desc}. <br><a href='/'>Return to Dashboard</a>", 400

        refresh_token = data.get("refresh_token")
        if refresh_token:
            set_key(".env", "SPOTIPY_CLIENT_ID", client_id)
            set_key(".env", "SPOTIPY_CLIENT_SECRET", client_secret)
            set_key(".env", "SPOTIFY_REFRESH_TOKEN", refresh_token)
            load_dotenv(override=True)
            return redirect("/?spotify_connected=1")
        else:
            return "Failed to receive refresh token from Spotify. <br><a href='/'>Return to Dashboard</a>", 400
    except Exception as e:
        return f"Error exchanging token with Spotify: {e}. <br><a href='/'>Return to Dashboard</a>", 500


@app.route("/api/connect/spotify", methods=["POST"])
def connect_spotify():
    data = request.json or {}
    client_id = data.get("client_id", "").strip()
    client_secret = data.get("client_secret", "").strip()
    refresh_token = data.get("refresh_token", "").strip()

    if not client_id or not client_secret:
        return jsonify({"success": False, "error": "Client ID and Client Secret are required."}), 400

    # Test client credentials
    try:
        sp = SpotifyClient(client_id, client_secret, refresh_token)
        user_name = "Read-Only"
        if sp.is_authenticated_user:
            user_info = sp.sp.current_user()
            user_name = user_info.get("display_name") or user_info.get("id")

        # Save to .env
        set_key(".env", "SPOTIPY_CLIENT_ID", client_id)
        set_key(".env", "SPOTIPY_CLIENT_SECRET", client_secret)
        if refresh_token:
            set_key(".env", "SPOTIFY_REFRESH_TOKEN", refresh_token)

        load_dotenv(override=True)
        return jsonify({"success": True, "user": user_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/connect/ytmusic", methods=["POST"])
def connect_ytmusic():
    data = request.json or {}
    raw_input = data.get("raw_input", "").strip()
    if not raw_input:
        return jsonify({"success": False, "error": "No input provided."}), 400

    headers = extract_browser_auth(raw_input)
    if "cookie" not in headers or "__Secure-3PAPISID" not in headers["cookie"]:
        # Maybe it's a raw oauth.json string
        try:
            parsed = json.loads(raw_input)
            if "refresh_token" in parsed:
                with open("oauth.json", "w") as f:
                    json.dump(parsed, f, indent=2)
                set_key(".env", "YTM_OAUTH_JSON", raw_input)
                load_dotenv(override=True)
                return jsonify({"success": True, "method": "OAuth"})
        except Exception:
            pass

        return jsonify(
            {
                "success": False,
                "error": "Could not find __Secure-3PAPISID in the provided input. Make sure you copied request headers or cURL from music.youtube.com.",
            }
        ), 400

    if "x-goog-authuser" not in headers:
        headers["x-goog-authuser"] = "0"
    if "authorization" not in headers or "SAPISIDHASH" not in headers["authorization"]:
        headers["authorization"] = "SAPISIDHASH dummy"

    # Save to browser.json
    with open("browser.json", "w") as f:
        json.dump(headers, f, indent=2)

    compact = json.dumps(headers)
    set_key(".env", "YTM_BROWSER_JSON", compact)
    load_dotenv(override=True)

    return jsonify({"success": True, "method": "Browser Headers"})


@app.route("/api/playlists/<platform>", methods=["GET"])
def get_playlists(platform):
    cfg = Config()
    if platform == "spotify":
        try:
            sp = SpotifyClient(cfg.spotify_client_id, cfg.spotify_client_secret, cfg.spotify_refresh_token)
            return jsonify({"success": True, "playlists": sp.get_user_playlists()})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
    elif platform == "ytmusic":
        try:
            yt = YTMusicClient(cfg.ytm_oauth_json, cfg.ytm_browser_json, cfg.ytm_client_id, cfg.ytm_client_secret)
            return jsonify({"success": True, "playlists": yt.get_user_playlists()})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": False, "error": "Invalid platform"}), 400


@app.route("/api/pairs", methods=["GET"])
def get_pairs():
    return jsonify({"success": True, "pairs": load_pairs_from_storage()})


@app.route("/api/pairs", methods=["POST"])
def add_pair():
    data = request.json or {}
    source_platform = data.get("source_platform", "spotify")
    target_platform = "ytmusic" if source_platform == "spotify" else "spotify"

    source_raw = data.get("source_id", "").strip()
    target_raw = data.get("target_id", "auto").strip()
    pair_name = data.get("name", "").strip()

    source_id = (
        extract_spotify_playlist_id(source_raw)
        if source_platform == "spotify"
        else extract_ytmusic_playlist_id(source_raw)
    )

    target_id = target_raw
    if target_raw and target_raw.lower() not in ("auto", "new", "create"):
        target_id = (
            extract_ytmusic_playlist_id(target_raw)
            if target_platform == "ytmusic"
            else extract_spotify_playlist_id(target_raw)
        )

    if not source_id:
        return jsonify({"success": False, "error": "Source playlist URL or ID is required."}), 400

    cfg = Config()
    # Resolve names
    if not pair_name:
        try:
            if source_platform == "spotify":
                sp = SpotifyClient(cfg.spotify_client_id, cfg.spotify_client_secret, cfg.spotify_refresh_token)
                meta = sp.get_playlist_details(source_id)
                pair_name = meta.get("name") or "Spotify Mirror"
            else:
                yt = YTMusicClient(cfg.ytm_oauth_json, cfg.ytm_browser_json)
                meta = yt.get_playlist_details(source_id)
                pair_name = meta.get("name") or "YT Music Mirror"
        except Exception:
            pair_name = f"{source_platform.title()} Sync"

    pairs = load_pairs_from_storage()
    new_entry = {
        "id": int(time.time()),
        "name": pair_name,
        "source_platform": source_platform,
        "source_id": source_id,
        "target_platform": target_platform,
        "target_id": target_id or "auto",
    }
    pairs.append(new_entry)
    save_pairs_to_storage(pairs)

    return jsonify({"success": True, "pair": new_entry})


@app.route("/api/pairs/<int:idx>", methods=["DELETE"])
def delete_pair(idx):
    pairs = load_pairs_from_storage()
    if 0 <= idx < len(pairs):
        removed = pairs.pop(idx)
        save_pairs_to_storage(pairs)
        return jsonify({"success": True, "removed": removed})
    return jsonify({"success": False, "error": "Invalid index"}), 404


def run_sync_worker():
    sync_state["is_running"] = True
    sync_state["logs"] = []
    sync_state["current_task"] = "Initializing..."

    cfg = Config()
    pairs = load_pairs_from_storage()

    try:
        sp_client = SpotifyClient(cfg.spotify_client_id, cfg.spotify_client_secret, cfg.spotify_refresh_token)
        yt_client = YTMusicClient(cfg.ytm_oauth_json, cfg.ytm_browser_json, cfg.ytm_client_id, cfg.ytm_client_secret)

        results = []
        for i, p in enumerate(pairs, 1):
            sync_state["current_task"] = f"Processing Pair #{i}: {p['name']}"
            source_platform = p.get("source_platform", "spotify")
            source_id = p.get("source_id")
            target_id = p.get("target_id")

            if source_platform == "spotify":
                res = sync_spotify_to_ytmusic(sp_client, yt_client, source_id, target_id)
                results.append(res)
                # If target was auto-created, update stored pair ID
                if target_id in ("auto", "new", "create", "") and res.get("target_playlist_id"):
                    p["target_id"] = res["target_playlist_id"]
                    save_pairs_to_storage(pairs)
            else:
                res = sync_ytmusic_to_spotify(yt_client, sp_client, source_id, target_id)
                results.append(res)
                if target_id in ("auto", "new", "create", "") and res.get("target_playlist_id"):
                    p["target_id"] = res["target_playlist_id"]
                    save_pairs_to_storage(pairs)

        sync_state["last_result"] = results
        sync_state["current_task"] = "Completed successfully!"
    except Exception as e:
        logging.error(f"Sync failed with error: {e}")
        sync_state["current_task"] = f"Error: {e}"
    finally:
        sync_state["is_running"] = False
        sync_state["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")


@app.route("/api/sync", methods=["POST"])
def trigger_sync():
    if sync_state["is_running"]:
        return jsonify({"success": False, "error": "A sync is already in progress."}), 409

    t = threading.Thread(target=run_sync_worker, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Sync started in background."})


@app.route("/api/sync/status", methods=["GET"])
def get_sync_status():
    return jsonify(
        {
            "is_running": sync_state["is_running"],
            "current_task": sync_state["current_task"],
            "logs": sync_state["logs"][-50:],
            "last_result": sync_state["last_result"],
            "completed_at": sync_state["completed_at"],
        }
    )


@app.route("/api/export_github", methods=["GET"])
def export_github():
    cfg = Config()
    pairs = load_pairs_from_storage()

    github_pairs = []
    for p in pairs:
        if p["source_platform"] == "spotify":
            github_pairs.append(
                {
                    "spotify_id": p["source_id"],
                    "yt_id": p["target_id"],
                    "direction": "spotify_to_yt",
                }
            )
        else:
            github_pairs.append(
                {
                    "spotify_id": p["target_id"],
                    "yt_id": p["source_id"],
                    "direction": "yt_to_spotify",
                }
            )

    secrets = {
        "SPOTIPY_CLIENT_ID": cfg.spotify_client_id,
        "SPOTIPY_CLIENT_SECRET": cfg.spotify_client_secret,
        "SPOTIFY_REFRESH_TOKEN": cfg.spotify_refresh_token,
        "YTM_BROWSER_JSON": cfg.ytm_browser_json,
        "YTM_OAUTH_JSON": cfg.ytm_oauth_json,
        "SYNC_PAIRS": json.dumps(github_pairs),
    }

    return jsonify({"success": True, "secrets": secrets})


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("🚀 Starting SpotifyYTConnect Web Interface on http://127.0.0.1:5000")
    print("=" * 65)
    app.run(host="0.0.0.0", port=5000, debug=False)
