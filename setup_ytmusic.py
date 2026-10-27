#!/usr/bin/env python3
"""
YouTube Music Authentication Setup Helper.
Provides an easy 15-second browser copy method (zero Google Cloud required)
as well as standard Google Cloud OAuth.
"""

import json
import os
import re
import sys
from ytmusicapi import YTMusic
from dotenv import load_dotenv

load_dotenv()


def extract_browser_auth(raw_input: str) -> dict:
    """Extracts YouTube Music headers from cURL commands, raw headers, or cookie strings."""
    raw = raw_input.strip()
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://music.youtube.com",
        "x-origin": "https://music.youtube.com",
        "authorization": "SAPISIDHASH dummy",
        "x-goog-authuser": "0",
    }

    # Case 1: Raw cookie string pasted directly
    if "__Secure-3PAPISID=" in raw and not any(k in raw.lower() for k in ["curl ", "-h ", "http:", "https:"]):
        headers["cookie"] = raw
        return headers

    # Case 2: cURL command format (Chrome, Edge, Brave, Firefox)
    curl_matches = re.findall(
        r"(?:-H|--header)\s+[\x27\x22]([^:]+):\s*(.*?)[\x27\x22]",
        raw,
        re.DOTALL | re.IGNORECASE,
    )
    if curl_matches:
        for k, v in curl_matches:
            headers[k.strip().lower()] = v.strip()
        if "cookie" in headers:
            return headers

    # Case 3: Line-by-line DevTools Request Headers format
    for line in raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("GET ") or line.startswith("POST ") or line.startswith("curl "):
            continue
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k.strip().lower()] = v.strip()
        elif ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    return headers


def setup_via_browser():
    print("\n" + "=" * 65)
    print("⚡ 15-SECOND BROWSER SETUP (Zero Google Cloud, Zero API Keys)")
    print("=" * 65)
    print("1. Open https://music.youtube.com in your browser (logged into your account).")
    print("2. Press F12 to open Developer Tools, then click the 'Network' tab.")
    print("3. Click any song, album, or playlist on YouTube Music.")
    print("4. In the Network tab, right-click any request (e.g. 'browse', 'next', 'player'):")
    print("     👉 Chrome / Edge / Brave: Right-click -> Copy -> 'Copy as cURL'")
    print("     👉 Firefox: Right-click -> Copy Value -> 'Copy Request Headers'")
    print("5. Paste it below and press Enter twice (or type 'DONE' on a new line):\n")

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "DONE":
                break
            lines.append(line)
            # If user pasted a single-line cURL or cookie and hit enter twice
            if len(lines) >= 1 and not line.strip():
                break
        except EOFError:
            break

    raw_pasted = "\n".join(lines).strip()
    if not raw_pasted:
        print("❌ No input detected. Aborted.")
        return

    headers = extract_browser_auth(raw_pasted)
    if "cookie" not in headers or "__Secure-3PAPISID" not in headers["cookie"]:
        print("\n❌ Missing required authentication cookie (__Secure-3PAPISID).")
        print("Make sure you are logged in to music.youtube.com and copied a valid request.")
        return

    # Ensure required fields for ytmusicapi
    if "x-goog-authuser" not in headers:
        headers["x-goog-authuser"] = "0"
    if "authorization" not in headers or "SAPISIDHASH" not in headers["authorization"]:
        headers["authorization"] = "SAPISIDHASH dummy"

    # Test the connection live
    print("\nTesting connection to YouTube Music API...")
    try:
        yt = YTMusic(auth=headers)
        # Test basic call
        yt.get_library_playlists(limit=1)
        print("✅ Connection verified! YouTube Music authenticated successfully.")
    except Exception as e:
        print(f"⚠️ Warning during verification test ({e}), but proceeding to save...")

    # Save to local browser.json
    with open("browser.json", "w") as f:
        json.dump(headers, f, indent=2)

    compact_json = json.dumps(headers)

    print("\n" + "=" * 65)
    print("🎉 SUCCESS! Generated browser.json successfully.")
    print("=" * 65)
    print("\nTo use this in GitHub Actions:")
    print("1. In your GitHub Repo, go to Settings -> Secrets and variables -> Actions")
    print("2. Add a new repository secret named:")
    print("   👉 YTM_BROWSER_JSON")
    print("3. Paste the following JSON text as the secret value:\n")
    print(compact_json)
    print("\n" + "=" * 65)


def setup_via_oauth():
    print("\n" + "=" * 65)
    print("Google Cloud OAuth Setup")
    print("=" * 65)
    print("Prerequisite: A Google Cloud Project with 'YouTube Data API v3' enabled.")
    print("1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials")
    print("2. Create Credentials -> OAuth Client ID")
    print("3. Choose Application Type: 'TVs and Limited Input devices' (or 'Desktop App')")
    print("4. Copy your Client ID and Client Secret.\n")

    client_id = os.getenv("YTM_CLIENT_ID") or input("Enter Google Client ID: ").strip()
    client_secret = os.getenv("YTM_CLIENT_SECRET") or input("Enter Google Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required for OAuth.")
        return

    from ytmusicapi.setup import setup_oauth
    print("\nStarting Device Authorization...")
    try:
        setup_oauth(
            client_id=client_id,
            client_secret=client_secret,
            filepath="oauth.json",
            open_browser=True,
        )

        with open("oauth.json", "r") as f:
            data = json.load(f)

        data["client_id"] = client_id
        data["client_secret"] = client_secret

        with open("oauth.json", "w") as f:
            json.dump(data, f, indent=2)

        compact_json = json.dumps(data)

        print("\n" + "=" * 65)
        print("🎉 SUCCESS! Generated oauth.json successfully.")
        print("=" * 65)
        print("\nTo use this in GitHub Actions:")
        print("1. In GitHub, go to Settings -> Secrets and variables -> Actions")
        print("2. Add a new repository secret named: YTM_OAUTH_JSON")
        print("3. Paste the following JSON text as the secret value:\n")
        print(compact_json)
        print("\n" + "=" * 65)

    except Exception as e:
        print(f"\n❌ Error setting up OAuth: {e}")


def main():
    print("=" * 65)
    print("YouTube Music Authentication Setup Helper")
    print("=" * 65)
    print("Choose an authentication method:")
    print("  [1] ⚡ 15-Second Browser Copy (Recommended: Fast, Zero Google Cloud setup)")
    print("  [2] 🔑 Google Cloud OAuth (Requires Google Cloud Project & YouTube Data API)")

    choice = input("\nEnter choice [1 or 2] (Default is 1): ").strip()
    if choice == "2":
        setup_via_oauth()
    else:
        setup_via_browser()


if __name__ == "__main__":
    main()
