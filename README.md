[GitHub Stars](https://github.com/adelelawady/synciflow/stargazers)
[GitHub Forks](https://github.com/adelelawady/synciflow/network/members)
[GitHub Issues](https://github.com/adelelawady/synciflow/issues)
[GitHub License](LICENSE)
[Repo Size](https://github.com/adelelawady/synciflow)
[Last Commit](https://github.com/adelelawady/synciflow/commits/main)
[Top Language](https://github.com/adelelawady/synciflow)

[![GitHub stars](https://img.shields.io/github/stars/adelelawady/synciflow?style=for-the-badge)](https://github.com/adelelawady/synciflow)
[![GitHub forks](https://img.shields.io/github/forks/adelelawady/synciflow?style=for-the-badge)](https://github.com/adelelawady/synciflow)
[![GitHub issues](https://img.shields.io/github/issues/adelelawady/synciflow?style=for-the-badge)](https://github.com/adelelawady/synciflow/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/adelelawady/synciflow?style=for-the-badge)](https://github.com/adelelawady/synciflow)
[![Repo size](https://img.shields.io/github/repo-size/adelelawady/synciflow?style=for-the-badge)](https://github.com/adelelawady/synciflow)
[![License](https://img.shields.io/github/license/adelelawady/synciflow?style=for-the-badge)](https://github.com/adelelawady/synciflow)

[![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-runtime-green?style=flat-square&logo=node.js)](https://nodejs.org/)
[![Electron](https://img.shields.io/badge/Electron-desktop-blue?style=flat-square&logo=electron)](https://www.electronjs.org/)
[![Spotify](https://img.shields.io/badge/Spotify-integration-1DB954?style=flat-square&logo=spotify)](https://spotify.com)


---

## 🚀 synciflow

**synciflow** is an offline-first music library and sync tool that lets you:

- Ingest tracks and playlists from **Spotify URLs**
- Resolve and download high‑quality audio via **YouTube**
- Store everything locally in a structured **SQLite + filesystem** library
- Interact through a **rich TUI-like CLI** and a **FastAPI HTTP API**

Ideal for building a private, self‑hosted music collection that mirrors your Spotify playlists, with full control over files on disk.

---

## ✨ Features

- **Offline library from Spotify URLs**  
  - Load individual tracks or entire playlists by Spotify URL.
  - Metadata (title, artist, artwork) stored in SQLite.
- **Spotify Liked Songs as a playlist**  
  - Use `syncify-py`'s login-based likes scraping to mirror your Spotify Liked Songs.
  - Exposed locally as a pseudo-playlist with stable `playlist_id` of `likes`.
  - Can be listed, inspected, and exported just like any other playlist.
- **Automated YouTube resolution & download**  
  - Resolves Spotify tracks to YouTube using Selenium + headless Chrome.
  - Downloads audio with `yt-dlp` and converts to high‑quality MP3 via `ffmpeg`.
- **Cover art embedding**  
  - Downloads artwork and embeds it directly into MP3 files via `mutagen`.
- **Playlist sync engine**  
  - Keeps a local playlist in sync with the current Spotify playlist contents.
  - Adds new tracks, prunes removed ones, and cleans up unreferenced files.
- **Structured local storage**  
  - Deterministic path layout under `storage_data/` for tracks, temp files, and playlist metadata.
  - Track filenames automatically sanitized and normalized.
- **Two CLIs**  
  - **Basic CLI** (`synciflow ...`) for scripting and automation.
  - **Smart CLI** (`synciflow smart`) with rich, interactive menus powered by `rich`.
- **HTTP API**  
  - FastAPI app exposing endpoints to:
    - Load tracks/playlists
    - Sync playlists
    - List tracks/playlists
    - Stream or download MP3s and playlist ZIPs.
- **Job tracking & notifications**  
  - Long-running tasks (track/playlist load, sync) run in the background and are tracked in a SQLite `jobs` table.
  - Real-time updates over a WebSocket (`/ws/notifications`) for progress and completion events.
  - CLI commands show Rich progress bars for playlist download, track download, and sync.

---

## 🧠 How It Works

At a high level:

1. **Input**: You provide a Spotify track or playlist URL, or trigger a Liked Songs sync.
2. **Metadata fetch**: `syncify` (external library) is used to obtain structured metadata:
  - Track: ID, title, artist, image URL.
  - Playlist: ID, title, image, track URLs.
  - Liked Songs: a list of liked track URLs scraped after you log into Spotify in a browser window.
3. **Resolution**: For each track, synciflow:
  - Searches YouTube via Selenium headless Chrome.
  - Resolves a YouTube video ID for that track/artist pair.
4. **Download**:
  - Uses `yt-dlp` to download the audio.
  - Uses `ffmpeg` to convert into a high‑quality MP3.
5. **Library storage**:
  - Files are moved atomically into `storage_data/tracks/<prefix>/<track_id>.mp3`.
  - Metadata is stored in SQLite via `SQLModel` (`Track`, `Playlist`, `PlaylistTrack`).
6. **Serving & tooling**:
  - CLI commands and FastAPI endpoints operate against this local library.
  - Playlists can be exported as ZIPs with embedded cover art and nice filenames.

### Core Components

- **Library orchestration**: `Library` (in `core/library_manager.py`) wires together:
  - `AppConfig` (paths, database location)
  - SQLite engine + migrations (`db/database.py`)
  - Filesystem layout (`storage/file_manager.py`, `storage/path_manager.py`)
  - Managers: `TrackManager`, `PlaylistManager`, `SyncManager`.
- **Track management**: `TrackManager`  
Handles:
  - Loading tracks by Spotify URL (`load_track`)
  - Local‑first loading from existing MP3s (`load_local`)
  - Triggering YouTube resolution + download pipeline.
- **Playlist management**: `PlaylistManager`  
Handles:
  - Loading playlists by Spotify URL (`load_playlist`)
  - Persisting playlist metadata to JSON in `storage_data/playlists/`
  - Rebuilding playlist/track relations from local files (`load_local`).
- **Sync engine**: `SyncManager`  
Compares current Spotify track set vs. local DB, then:
  - Adds missing tracks.
  - Rebuilds ordered relations.
  - Removes unreferenced tracks from DB and disk.
- **API layer**: `api/server.py`  
FastAPI app with endpoints for loading, listing, streaming, and exporting.
- **Job tracking**: `core/job_manager.py`  
Creates and updates jobs (pending → running → completed/failed) in the `jobs` table. Used by the API to return a `job_id` immediately and run work in a background thread.
- **Notification bus**: `core/notification_bus.py`  
Thread-safe event bus: sync code (e.g. background workers) publishes events via `publish_sync()`; a bridge task forwards them to async subscribers. WebSocket clients subscribe to receive real-time events (e.g. `PLAYLIST_PROGRESS`, `TRACK_DOWNLOAD_COMPLETED`, `ERROR`).

---

## 🛠 Tech Stack

- **Language**: Python 3.10+
- **Runtime & tooling**:
  - [FastAPI](https://fastapi.tiangolo.com/) – HTTP API
  - [Typer](https://typer.tiangolo.com/) – CLI
  - [Rich](https://rich.readthedocs.io/) – interactive smart CLI
  - [SQLModel](https://sqlmodel.tiangolo.com/) + SQLite – persistence
- **Audio & metadata**:
  - [yt-dlp](https://github.com/yt-dlp/yt-dlp) – YouTube downloader
  - [ffmpeg](https://ffmpeg.org/) – audio conversion
  - [mutagen](https://mutagen.readthedocs.io/) – MP3 tag manipulation
- **Automation**:
  - [Selenium](https://www.selenium.dev/) + Chrome / Chromium
  - [webdriver-manager](https://github.com/SergeyPirogov/webdriver_manager)
- **Other**:
  - `pydantic`, `dataclasses`, `pathlib`, `zipfile`, etc.

---

## 📦 Installation

> **Note:** The project is laid out as a Python package under `src/synciflow`.  
> The examples below assume you have cloned the repository locally.

### 1. Clone the repository

```bash
git clone https://github.com/adelelawady/synciflow.git
cd synciflow
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install in editable (development) mode

If your `pyproject.toml` defines `dev` extras (recommended):

```bash
pip install -e ".[dev]"
```

If not, install core dependencies manually (example):

```bash
pip install -e .
# plus system-level tools like ffmpeg and Chrome; see below
```

### 4. System dependencies

You will need:

- **ffmpeg** (in your `PATH`)
- **Google Chrome / Chromium** (for Selenium)
- Ability to run a **headless Chrome** (X11/Wayland or Windows environment)
- Network access to:
  - `open.spotify.com` (via the `syncify` library)
  - `youtube.com` and `ytimg.com`

### Building a standalone executable

You can build a single Windows executable so you can run synciflow without installing Python or dependencies.

1. Install the project and build dependencies (from the repo root):
  ```bash
   pip install -e .
   pip install hatch
  ```
2. Build the exe with one command (from the repo root, with your venv activated):
  ```bash
  python -m hatch build --target pyinstaller
  ```
   If `hatch` is not on your PATH, use:
3. The executable is written to `dist/synciflow.exe`. Copy it to any Windows machine; external tools (ffmpeg, Chrome) must still be available on that machine as described in **System dependencies** above.

This build produces a Windows exe. Building on Linux or macOS with the same command produces a binary for that OS; PyInstaller does not support cross-compilation.

---

## ⚙️ Configuration

Runtime configuration is primarily path‑based and handled via `AppConfig`:

```python
from pathlib import Path
from synciflow.config import AppConfig

cfg = AppConfig(
    storage_root=Path("storage_data"),  # where MP3s and playlist metadata go
    data_root=Path("data"),            # where SQLite DB lives
)
```

By default (`AppConfig()`):

- **Database**: `data/synciflow.sqlite3`
- **Storage root**: `storage_data/`
  - Tracks: `storage_data/tracks/<prefix>/<track_id>.mp3`
  - Temp files: `storage_data/tmp/`
  - Playlist metadata JSON: `storage_data/playlists/<playlist_id>.json`

The CLI and API entrypoints construct `AppConfig()` with default paths. If you embed synciflow in your own Python app, you can create a `Library` with a custom config:

```python
from synciflow.core.library_manager import Library
from synciflow.config import AppConfig

lib = Library.create(AppConfig(storage_root=Path("/my/music"), data_root=Path("/my/db")))
```

### Environment variables

synciflow itself does **not** hard‑code environment variables, but its dependencies may require them (e.g. `syncify` for Spotify credentials). A typical setup might include:


| Variable            | Required | Description                                  |
| ------------------- | -------- | -------------------------------------------- |
| `SPOTIFY_CLIENT_ID` | Maybe    | Used by the `syncify` library (if required). |
| `SPOTIFY_SECRET`    | Maybe    | Used by the `syncify` library (if required). |


Refer to the `syncify` project documentation for exact Spotify configuration requirements.

---

## 🚀 Usage

Once installed (and virtualenv activated), you should have a `synciflow` CLI entrypoint.

### CLI – Basic commands

Track, playlist, and sync commands show **Rich progress bars** (e.g. “Downloading track…”, “Loading playlist…”, “Syncing playlist…”) while work runs.

#### Load a single track from Spotify

```bash
synciflow track "https://open.spotify.com/track/XXXXXXXXXXXXXXX"
```

Outputs:

- Track title and artist
- Internal `track_id`
- Local audio file path (once downloaded)

#### Load a playlist from Spotify

```bash
synciflow playlist "https://open.spotify.com/playlist/YYYYYYYYYYYYYYY"
```

Outputs:

- Playlist title
- Internal `playlist_id`

#### Sync your Spotify Liked Songs as a playlist

```bash
synciflow likes
```

This will:

- Open a browser window (via `syncify-py`) so you can log into Spotify.
- Scrape your Liked Songs and sync them into a local pseudo-playlist with `playlist_id=likes`.

After that, you can treat `likes` like any other playlist:

```bash
synciflow playlist-local likes
synciflow download-playlist-zip likes /path/to/output
synciflow save-playlist likes /path/to/output
```

#### Sync an existing playlist to the latest Spotify state

```bash
synciflow sync "https://open.spotify.com/playlist/YYYYYYYYYYYYYYY"
```

Outputs a summary:

```text
added=10 removed=2 kept=50
```

#### List tracks and playlists

```bash
synciflow tracks
synciflow playlists
```

#### Download / export tracks

```bash
# Print the path to an existing track by ID
synciflow download-track <track_id>

# Save a track to a specific file or directory
synciflow save-track <track_id> /path/to/output_or_directory
```

#### Export playlists as ZIP

```bash
# Build a playlist ZIP and save to a file/directory
synciflow download-playlist-zip <playlist_id> /path/to/output_or_directory

# Or use smart naming based on playlist title
synciflow save-playlist <playlist_id> /path/to/output_or_directory
```

### Smart CLI – Interactive mode

Launch the full‑screen style interactive CLI:

```bash
synciflow smart
```

From there you can:

- Load tracks/playlists by URL or ID
- List tracks/playlists
- Save tracks or playlists to files/ZIPs
- Inspect and delete tracks or playlists from the DB

### HTTP API & Frontend UI – Development / Production server

Run the combined FastAPI API **and** React frontend UI via the CLI:

```bash
synciflow serve --host 127.0.0.1 --port 8080
```

Then open `http://127.0.0.1:8080` in your browser to access the UI (which talks to the same server for API calls).

You can still run just the FastAPI app directly with `uvicorn` if you prefer:

```bash
uvicorn synciflow.api.server:create_app --factory --host 0.0.0.0 --port 8080
```

Once running, the API will be available at `http://127.0.0.1:8080` and, if the frontend build is present, the UI will be served from the same origin.

### Building and packaging the frontend UI

To include the React UI in your installation (wheel / sdist), build it before creating a release:

```bash
# from the project root
cd frontend
npm install
npm run build
```

Ensure the built assets are copied or moved into `src/synciflow/frontend` before running a Python build (for example with `hatch build` or `python -m build`). Those assets will then be bundled with the `synciflow` package and served automatically by `synciflow serve` on port 8080.

---

## 📡 API Reference

All endpoints are defined in `synciflow.api.server.create_app`.

### Load & sync (background jobs)

These endpoints create a job, return **202 Accepted** with `{ "job_id": "<uuid>" }`, and run the work in a background task. Use **GET /jobs/{job_id}** to poll status, or connect to **WebSocket /ws/notifications** for real-time progress.


| Method | Path             | Body example                     | Description                                                                                                  |
| ------ | ---------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| POST   | `/track/load`    | `{ "url": "<spotify_track>" }`   | Load a track by Spotify URL (download if needed). Returns 202 + `job_id`.                                    |
| POST   | `/playlist/load` | `{ "url": "<spotify_playlist>"}` | Load a playlist by Spotify URL, downloading tracks. Returns 202 + `job_id`.                                  |
| POST   | `/playlist/sync` | `{ "url": "<spotify_playlist>"}` | Sync a playlist to the latest Spotify track set. Returns 202 + `job_id`.                                     |
| POST   | `/likes/load`    | *no body*                        | Load your Spotify Liked Songs into a local pseudo-playlist with `playlist_id=likes`. Returns 202 + `job_id`. |
| POST   | `/likes/sync`    | *no body*                        | Sync the `likes` pseudo-playlist against the current Spotify Liked Songs set. Returns 202 + `job_id`.        |


### Jobs & notifications


| Method    | Path                | Description                                                                                                                                                                                                                                                     |
| --------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET       | `/jobs/{job_id}`    | Get job status: `job_id`, `job_type`, `status`, `progress`, `message`, `created_at`, `updated_at`.                                                                                                                                                              |
| WebSocket | `/ws/notifications` | Real-time events: `TRACK_DOWNLOAD_STARTED`, `TRACK_DOWNLOAD_COMPLETED`, `PLAYLIST_PROGRESS`, `PLAYLIST_COMPLETED`, `SYNC_PROGRESS`, `SYNC_COMPLETED`, `ERROR`. Each message is JSON with `event_type`, `job_id`, `progress`, `message`, and optional `payload`. |


**Flow:** A POST to `/track/load`, `/playlist/load`, or `/playlist/sync` creates a row in the `jobs` table (status `pending`), returns 202 with `job_id`, and starts a background thread. The thread updates the job (`running` → `completed` or `failed`) and publishes events to the notification bus. Clients can poll `GET /jobs/{job_id}` or subscribe to `ws://host/ws/notifications` to receive progress and completion events.

### Local-first load


| Method | Path                                 | Description                                          |
| ------ | ------------------------------------ | ---------------------------------------------------- |
| POST   | `/track/{track_id}/load_local`       | Register/repair a track from a local MP3.            |
| POST   | `/playlist/{playlist_id}/load_local` | Load playlist from stored metadata and local tracks. |


### Querying library


| Method | Path                             | Description                        |
| ------ | -------------------------------- | ---------------------------------- |
| GET    | `/track/{track_id}`              | Get track metadata from DB.        |
| GET    | `/playlist/{playlist_id}`        | Get playlist metadata from DB.     |
| GET    | `/tracks`                        | List all tracks.                   |
| GET    | `/playlists`                     | List all playlists.                |
| GET    | `/playlist/{playlist_id}/tracks` | Get ordered tracks for a playlist. |


### Streaming & download


| Method | Path                                   | Description                               |
| ------ | -------------------------------------- | ----------------------------------------- |
| GET    | `/track/{track_id}/stream`             | Stream MP3 for a track.                   |
| GET    | `/track/{track_id}/download`           | Download MP3 for a track (nice filename). |
| GET    | `/playlist/{playlist_id}/download.zip` | Download ZIP of playlist tracks.          |


---

## 📂 Project Structure

A high‑level overview of the key directories and modules:

```text
synciflow/
├─ src/
│  └─ synciflow/
│     ├─ __init__.py                 # Package metadata (__version__)
│     ├─ config.py                   # AppConfig: storage + DB paths
│     ├─ cli/
│     │  ├─ __init__.py
│     │  ├─ main.py                  # Typer CLI entrypoint (synciflow ...)
│     │  └─ smart.py                 # Rich-powered interactive CLI
│     ├─ api/
│     │  ├─ __init__.py
│     │  └─ server.py                # FastAPI app + endpoints
│     ├─ core/
│     │  ├─ __init__.py
│     │  ├─ utils.py                 # ID extraction, filename sanitization
│     │  ├─ library_manager.py       # Library: ties DB + storage + managers
│     │  ├─ track_manager.py         # Track loading/downloading logic
│     │  ├─ playlist_manager.py      # Playlist loading, metadata, relations
│     │  ├─ sync_manager.py          # Playlist sync against Spotify
│     │  ├─ job_manager.py           # Job CRUD: create_job, update_job_progress, complete_job, fail_job, get_job
│     │  └─ notification_bus.py     # Event bus: publish_sync, subscribe, bridge for WebSocket
│     ├─ db/
│     │  ├─ __init__.py
│     │  ├─ models.py                # SQLModel tables: Track, Playlist, PlaylistTrack, Job
│     │  └─ database.py              # SQLite engine + session helpers
│     ├─ storage/
│     │  ├─ __init__.py
│     │  ├─ path_manager.py          # StoragePaths, track paths, metadata paths
│     │  ├─ file_manager.py          # FileManager: atomic moves, deletes, tmp copies
│     │  ├─ playlist_metadata.py     # JSON metadata read/write for playlists
│     │  └─ zip_builder.py           # ZIP creation for playlists
│     ├─ schemas/
│     │  ├─ __init__.py
│     │  ├─ track.py                 # TrackDetails dataclass
│     │  └─ playlist.py              # PlaylistDetails dataclass
│     └─ services/
│        ├─ __init__.py
│        ├─ spotify_client.py        # Thin adapter to syncify.get_track/get_playlist
│        ├─ tagging.py               # Cover art embedding into MP3s
│        ├─ downloader.py            # Download pipeline: YouTube -> tmp MP3
│        └─ youtube.py               # Selenium + yt-dlp + ffmpeg utilities
├─ storage_data/                      # Default storage root (created at runtime)
└─ data/                              # Default SQLite DB path (created at runtime)
```

---

## 🖼 Screenshots

### Console (CLI)

<table>
<tr>
<td><img src="docs/images/Application%20Console%20Cli%20View%20help.png" width="480" alt="CLI help view" title="CLI help view" /></td>
<td><img src="docs/images/Application%20Console%20Smart%20Cli%20View.png" width="480" alt="Smart CLI main view" title="Smart CLI main view" /></td>
</tr>
<tr>
<td align="center"><em>CLI help view</em></td>
<td align="center"><em>Smart CLI main view</em></td>
</tr>
<tr>
<td><img src="docs/images/Application%20Console%20Smart%20Cli%20Use%20View.png" width="480" alt="Smart CLI use view" title="Smart CLI use view" /></td>
<td><img src="docs/images/Application%20Console%20Serve%20Api%20View.png" width="480" alt="Serve API view" title="Serve API view" /></td>
</tr>
<tr>
<td align="center"><em>Smart CLI use view</em></td>
<td align="center"><em>Serve API view</em></td>
</tr>
</table>

### Web UI (Windows)

<table>
<tr>
<td><img src="docs/images/Application%20Ui%20Windows%20You%20Library.png" width="480" alt="Your library" title="Your library" /></td>
<td><img src="docs/images/Application%20Ui%20Windows%20Likes%20List.png" width="480" alt="Likes list" title="Likes list" /></td>
</tr>
<tr>
<td align="center"><em>Your library</em></td>
<td align="center"><em>Likes list</em></td>
</tr>
<tr>
<td><img src="docs/images/Application%20Ui%20Windows%20View%20Playlist.png" width="480" alt="View playlist" title="View playlist" /></td>
<td><img src="docs/images/Application%20Ui%20Windows%20Playlist%20Page%20View.png" width="480" alt="Playlist page view" title="Playlist page view" /></td>
</tr>
<tr>
<td align="center"><em>View playlist</em></td>
<td align="center"><em>Playlist page view</em></td>
</tr>
</table>

---

## 🧪 Development

### Set up for development

```bash
git clone https://github.com/adelelawady/synciflow.git
cd synciflow

python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

### Run tests

If a test suite is configured (e.g. with `pytest`):

```bash
pytest
```

### Run the CLI locally

```bash
synciflow smart
synciflow track "https://open.spotify.com/track/XXXXXXXXXXXXXXX"
```

### Run the API locally

```bash
uvicorn synciflow.api.server:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000` or add a docs UI (e.g. via FastAPI’s automatic docs if enabled).

---

## 🤝 Contributing

Contributions are very welcome!

- **Bug reports & feature requests**:  
Open an issue with a clear description and, if possible, reproduction steps.
- **Pull requests**:
  1. Fork the repo.
  2. Create a feature branch:
    ```bash
     git checkout -b feature/my-awesome-idea
    ```
  3. Make your changes, add tests where appropriate.
  4. Run the test suite (and format/lint, if configured).
  5. Open a Pull Request describing:
    - What you changed
    - Why it’s useful
    - Any breaking changes or migration notes

Please keep code style consistent with the existing project and prefer small, focused PRs.

---

## 📜 License

This project is open source.  
See the `LICENSE` file in the repository for the full license text.

---

## ⭐ Support

If you find **synciflow** useful:

- **Star the repository** on GitHub – it really helps others discover the project.
- **Share it** with friends or colleagues who might benefit from an offline, scriptable music library.

```text
If you like it, star it ⭐
```

