#!/usr/bin/env python3
"""
YouTube Music One-Time Authentication Setup Helper.
Generates oauth.json or browser.json for YouTube Music account access.
"""

import json
import os
import sys
from ytmusicapi.setup import setup_oauth, setup_browser
from dotenv import load_dotenv

load_dotenv()


def setup_via_oauth():
    print("\n--- Method 1: Google Cloud OAuth (Recommended for CI/CD) ---")
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

    print("\nStarting Device Authorization...")
    try:
        # Runs the interactive device authorization prompt
        setup_oauth(
            client_id=client_id,
            client_secret=client_secret,
            filepath="oauth.json",
            open_browser=True,
        )

        # Ensure client_id and client_secret are preserved in oauth.json
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


def setup_via_browser():
    print("\n--- Method 2: Browser Headers Setup (Quick Cookie Method) ---")
    print("1. Open https://music.youtube.com in your browser (logged in).")
    print("2. Open Developer Tools (F12) -> Network tab.")
    print("3. Filter by 'browse' or click on any playlist / album.")
    print("4. Right click the request -> Copy -> Copy request headers.")
    print("5. Paste below:\n")

    try:
        setup_browser(filepath="browser.json")
        with open("browser.json", "r") as f:
            content = f.read()

        print("\n" + "=" * 65)
        print("🎉 SUCCESS! Generated browser.json successfully.")
        print("=" * 65)
        print("\nTo use this in GitHub Actions:")
        print("1. Add a secret named: YTM_BROWSER_JSON")
        print("2. Paste the contents of browser.json as the value.\n")
    except Exception as e:
        print(f"\n❌ Error setting up browser headers: {e}")


def main():
    print("=" * 65)
    print("YouTube Music Authentication Setup")
    print("=" * 65)
    print("Choose your preferred setup method:")
    print("  [1] Google Cloud OAuth (Recommended: long-lasting, stable in CI/CD)")
    print("  [2] Browser Headers Cookie (Fast setup, but cookies may expire periodically)")

    choice = input("\nEnter choice [1 or 2]: ").strip()
    if choice == "1":
        setup_via_oauth()
    elif choice == "2":
        setup_via_browser()
    else:
        print("Invalid option selected. Exiting.")


if __name__ == "__main__":
    main()
