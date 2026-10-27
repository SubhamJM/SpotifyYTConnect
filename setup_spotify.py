#!/usr/bin/env python3
"""
Spotify One-Time OAuth Setup Helper.
Run this script locally to generate your SPOTIFY_REFRESH_TOKEN.
"""

import os
import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

REDIRECT_URI = "http://127.0.0.1:9090"
SCOPE = "playlist-modify-public playlist-modify-private playlist-read-private"


def main():
    print("=" * 65)
    print("Spotify One-Time Account Authorization Helper")
    print("=" * 65)
    print("1. Go to https://developer.spotify.com/dashboard and select/create your app.")
    print("2. In App Settings, add this Redirect URI exactly:")
    print(f"   👉 {REDIRECT_URI}")
    print("3. Click Save in the Spotify Dashboard.\n")

    client_id = os.getenv("SPOTIPY_CLIENT_ID") or input("Enter your Spotify Client ID: ").strip()
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET") or input("Enter your Spotify Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required!")
        sys.exit(1)

    print("\nOpening your browser for Spotify authorization...")
    oauth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=True,
    )

    try:
        auth_url = oauth_manager.get_authorize_url()
        print(f"\nIf your browser doesn't open automatically, visit:\n{auth_url}\n")

        # Automatically opens browser or listens on local port 9090
        token_info = oauth_manager.get_access_token(oauth_manager.get_auth_response())

        refresh_token = token_info.get("refresh_token")
        if not refresh_token:
            print("Failed to obtain refresh token. Please try again.")
            sys.exit(1)

        print("\n" + "=" * 65)
        print("🎉 SUCCESS! Authorization completed.")
        print("=" * 65)
        print(f"\nYour Spotify Refresh Token is:\n")
        print(f"👉 {refresh_token}\n")
        print("Save this in your repository's GitHub Secrets as: SPOTIFY_REFRESH_TOKEN")
        print("Also save SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in GitHub Secrets.")

        # Update local .env file if it exists
        if os.path.exists(".env"):
            with open(".env", "a") as f:
                f.write(f"\nSPOTIFY_REFRESH_TOKEN=\"{refresh_token}\"\n")
            print("Updated your local .env file with SPOTIFY_REFRESH_TOKEN.")

    except Exception as e:
        print(f"\n❌ Error during authorization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
