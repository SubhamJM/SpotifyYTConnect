# SpotifyYTConnect 🎵🔄🎧

An automated, serverless, 2-way playlist synchronizer between **Spotify** and **YouTube Music** powered by Python and **GitHub Actions**.

No paid subscriptions, no third-party web services. Your playlists stay in continuous sync running entirely on GitHub's free scheduled CI/CD runners.

---

## 🌟 Key Features

* **Dedicated Mirror Playlists (Separate Copies):**
  * Auto-creates and maintains an independent clone on the target platform (e.g. Spotify `"for You"` $\rightarrow$ YouTube Music `"for You"`, and YouTube Music `"idk"` $\rightarrow$ Spotify `"idk"`).
  * No mixing or jumbling different playlists together.
* **TuneMyMusic-Style Web Interface:**
  * Intuitive browser dashboard (`python web_app.py`) to connect Spotify & YouTube Music, browse playlists, create mirror pairs, and run one-click syncs.
* **15-Second YouTube Music Setup:** No Google Cloud or API keys required—just copy request headers or cURL from your browser.
* **Intelligent Metadata Matching:**
  * Strips video noise tags (e.g., `(Official Audio)`, `[Visualizer]`, `[MV]`, `(feat. ...)`).
  * Prioritizes official audio studio tracks (`filter="songs"`) on YouTube Music.
  * Validates song durations (tolerance $\pm$ 8s) to avoid matching 10-hour loops, live tracks, or video intros.
* **100% Free & Serverless Automation:** Run locally anytime via web UI or automatically every 4 hours via GitHub Actions.

---

## 🖥️ Web Interface (TuneMyMusic Style)

Prefer an interactive visual dashboard instead of editing config files?

```bash
python web_app.py
```
Open **`http://127.0.0.1:5000`** in your browser to:
1. View connection status of your Spotify and YouTube Music accounts.
2. Add new mirror playlist pairs with 1-click **Auto-Create Clone**.
3. Hit **Sync Now** to watch songs match and sync with a live real-time progress console.
4. Click **Export for GitHub Actions** to copy your pre-filled secrets directly into GitHub.

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

### Step 3: YouTube Music Authorization (15 Seconds)

Whoever owns the YouTube Music playlist performs this step. **No Google Cloud setup or API keys are required!**

1. Open [music.youtube.com](https://music.youtube.com) in your browser (Chrome, Firefox, Edge, or Brave) while logged in to your account.
2. Press **F12** to open Developer Tools, then click the **Network** tab.
3. Click any song, album, or playlist on YouTube Music to trigger network traffic.
4. In the Network tab list, right-click any request (e.g. `browse`, `next`, or `player`):
   * **Chrome / Edge / Brave:** Right-click $\rightarrow$ **Copy** $\rightarrow$ **Copy as cURL**
   * **Firefox:** Right-click $\rightarrow$ **Copy Value** $\rightarrow$ **Copy Request Headers**
5. In your terminal, run:
   ```bash
   python setup_ytmusic.py
   ```
6. Select **Option 1** (Browser Setup), paste what you copied, and hit Enter.
7. The script automatically verifies your login, tests the YouTube Music API connection, and outputs your **`YTM_BROWSER_JSON`**!
8. Add this in your GitHub Repo under **Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions** as:
   `YTM_BROWSER_JSON`

*(Optional: If you prefer Google Cloud OAuth instead of browser headers, choose Option 2).*

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
