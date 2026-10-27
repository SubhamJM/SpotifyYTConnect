# SpotifyYTConnect 🎵🔄🎧

An automated, serverless, 2-way playlist synchronizer between **Spotify** and **YouTube Music** powered by Python and **GitHub Actions**.

No paid subscriptions, no third-party web services. Your playlists stay in continuous sync running entirely on GitHub's free scheduled CI/CD runners.

---

## 🌟 Key Features

* **Bi-directional or One-way Mirroring:**
  * Spotify $\rightarrow$ YouTube Music
  * YouTube Music $\rightarrow$ Spotify
  * Both ways (Bidirectional sync)
* **Intelligent Metadata Matching:**
  * Strips video noise tags (e.g., `(Official Audio)`, `[Visualizer]`, `[MV]`, `(feat. ...)`).
  * Prioritizes official audio studio tracks (`filter="songs"`) on YouTube Music.
  * Validates song durations (tolerance $\pm$ 8s) to avoid matching 10-hour loops, live tracks, or video intros.
* **100% Free & Serverless:** Runs automatically every 4 hours via GitHub Actions cron or on-demand with a click of a button.
* **Safe Credential Management:** Auth tokens are stored encrypted in GitHub Secrets and hydrated dynamically during execution.

---

## 📁 Project Structure

```text
SpotifyYTConnect/
├── .github/workflows/
│   └── sync.yml            # GitHub Actions cron & dispatch workflow
├── src/
│   ├── config.py           # Configuration loader & playlist URL parser
│   ├── matcher.py          # Fuzzy matching & metadata sanitizer
│   ├── spotify_client.py   # Spotify API integration (spotipy)
│   ├── ytmusic_client.py   # YouTube Music API integration (ytmusicapi)
│   └── syncer.py           # Diffing engine & sync orchestrator
├── setup_spotify.py        # One-time helper to get SPOTIFY_REFRESH_TOKEN
├── setup_ytmusic.py        # One-time helper to get YTM_OAUTH_JSON
├── main.py                 # Main sync entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
└── tests/                  # Unit tests
```

---

## 🚀 Setup Guide: What You and Your Friend Need to Do

Follow these steps once to configure the system. Once configured, it will run autonomously forever.

---

### Step 1: Clone and Prepare Locally

```bash
git clone git@github.com:SubhamJM/SpotifyYTConnect.git
cd SpotifyYTConnect

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 2: Spotify Credentials & Authorization

Whoever owns the destination Spotify playlist (or needs Spotify access) performs this step:

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**:
   * **App Name:** `SpotifyYTConnect`
   * **App Description:** `Personal Playlist Sync`
   * **Redirect URIs:** Add `http://127.0.0.1:9090` (⚠️ Crucial!)
   * Which API are you planning to use? Select **Web API**.
3. In your app dashboard, go to **Settings** and copy:
   * **Client ID**
   * **Client Secret**
4. Run the interactive Spotify setup script in your terminal:
   ```bash
   python setup_spotify.py
   ```
5. Enter your Client ID and Client Secret when prompted. Your browser will automatically open to authorize your Spotify account.
6. The script will output your **`SPOTIFY_REFRESH_TOKEN`**. Copy it down!

---

### Step 3: YouTube Music Authorization

Whoever owns the YouTube Music playlist performs this step:

Run the interactive setup helper:
```bash
python setup_ytmusic.py
```

You can choose either of two methods:

#### Method A: Google Cloud OAuth (Recommended for CI/CD)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a free project (e.g. `YTMusicSync`).
3. Under **APIs & Services** $\rightarrow$ **Library**, search for **YouTube Data API v3** and click **Enable**.
4. Go to **APIs & Services** $\rightarrow$ **OAuth consent screen**:
   * User Type: **External**
   * Fill in App Name and your email, then save.
   * Under **Test Users**, add your Google Account email!
5. Go to **APIs & Services** $\rightarrow$ **Credentials**:
   * Click **Create Credentials** $\rightarrow$ **OAuth client ID**.
   * Application type: **TVs and Limited Input devices** (or **Desktop App**).
6. Enter the Client ID and Secret in `python setup_ytmusic.py` (Option 1).
7. It will provide a link (`https://www.google.com/device`) and code. Open the link, sign in to your YouTube Music Google account, and enter the code.
8. The script saves `oauth.json` and prints the compact JSON text. Copy it!

#### Method B: Browser Headers (Quick Alternative)
If you don't want to create a Google Cloud project:
1. Run `python setup_ytmusic.py` and choose **Option 2**.
2. Follow the on-screen instructions to copy request headers from [music.youtube.com](https://music.youtube.com) DevTools.

---

### Step 4: Add Secrets to GitHub

Push your repository to GitHub:
```bash
git add .
git commit -m "Initial commit of SpotifyYTConnect"
git push -u origin master
```

In your GitHub repository:
1. Navigate to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
2. Click **New repository secret** for each of the following:

| Secret Name | Value | Required For |
| :--- | :--- | :--- |
| `SPOTIPY_CLIENT_ID` | Your Spotify Client ID | Spotify Read/Write |
| `SPOTIPY_CLIENT_SECRET` | Your Spotify Client Secret | Spotify Read/Write |
| `SPOTIFY_REFRESH_TOKEN` | Generated Spotify Refresh Token | Spotify Write / Private read |
| `YTM_OAUTH_JSON` | Full text of `oauth.json` | YouTube Music Read/Write |
| `SPOTIFY_PLAYLIST_ID` | Your Spotify playlist link or ID | Destination / Source Playlist |
| `YTMUSIC_PLAYLIST_ID` | Your YouTube Music playlist link or ID | Destination / Source Playlist |
| `SYNC_DIRECTION` | `both`, `spotify_to_yt`, or `yt_to_spotify` | (Default is `both`) |

> [!TIP]
> You can paste full playlist URLs like `https://open.spotify.com/playlist/37i9dQZF...` or `https://music.youtube.com/playlist?list=PL...`. The script automatically parses the raw playlist IDs.

---

### Step 5: Test and Run

1. Go to the **Actions** tab in your GitHub repository.
2. Select **Sync Music Playlists** in the left sidebar.
3. Click the **Run workflow** dropdown $\rightarrow$ **Run workflow**.
4. Click on the running job to inspect real-time sync logs!
5. From then on, GitHub Actions will automatically wake up **every 4 hours** and sync newly added songs.

---

## ⚙️ Advanced: Multiple Playlist Pairs

If you and your friend have multiple shared playlists to sync (e.g. *Chill Vibes*, *Workout*, *Rock*), you can define `SYNC_PAIRS` as a GitHub Secret or in `.env`:

```json
[
  {
    "spotify_id": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
    "yt_id": "https://music.youtube.com/playlist?list=PL4fGSIFgk54Vxyz123",
    "direction": "both"
  },
  {
    "spotify_id": "spotify:playlist:5xU65P2eWlXoYVbM7B5r",
    "yt_id": "PL4fGSIFgk54U89...",
    "direction": "spotify_to_yt"
  }
]
```

---

## 🧪 Local Testing

You can run the sync locally at any time:
```bash
# Copy example environment file
cp .env.example .env
# Fill in your IDs/credentials in .env
python main.py
```

Run test suite:
```bash
pytest
```

---

## 🔒 Security Best Practices

* Never commit `.env`, `oauth.json`, or `.cache` to git.
* The included `.gitignore` already blocks these files by default.
* GitHub Secrets are masked in Actions logs.
