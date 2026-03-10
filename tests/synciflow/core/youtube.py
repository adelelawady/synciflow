"""
youtube.py
----------
Utilities for resolving Spotify tracks to YouTube and downloading them
as MP3 files. This module is responsible for YouTube / download concerns,
while `spotify/Spotify_track_info.py` is kept as a Spotify-only helper.
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
import ffmpeg
from mutagen.mp3 import MP3
from mutagen.id3 import ID3

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
LOG = logging.getLogger("YouTubeDownloader")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class TrackDetails:
    """Minimal track details needed for YouTube search."""

    track_title: str
    artist_title: str


@dataclass
class TrackInfo:
    """Holds metadata for a downloaded track."""

    spotify_url: str
    youtube_video_id: str = ""
    youtube_url: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    year: str = ""
    duration_seconds: int = 0
    output_path: str = ""


def is_spotify_link(url: str) -> bool:
    return "open.spotify.com/track/" in (url or "")


def is_valid_youtube_url(url: str) -> bool:
    pattern = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/")
    return bool(pattern.search(url or ""))


def extract_youtube_video_id(url: str) -> str | None:
    if not url:
        return None
    # Standard watch URL
    match = re.search(r"v=([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    # Short youtu.be URL
    match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------
# Selenium-based scraping
# ---------------------------------------------------------------------------
def _build_chrome_driver() -> webdriver.Chrome:
    """
    Create a Chrome WebDriver with options suitable for YouTube scraping.

    Prefers Selenium Manager (Selenium 4+) to locate ChromeDriver; falls back
    to webdriver-manager when needed.
    """
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--incognito")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        return webdriver.Chrome(options=options)
    except WebDriverException:
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
# ---------------------------------------------------------------------------
# Audio metadata extraction
# ---------------------------------------------------------------------------
def populate_youtube_details_for_track(
    track_title: str, artist_title: str
) -> str:
    """
    Given a `TrackDetails` with at least `track_title` and `artist_title`
    populated, perform a YouTube search and return the YouTube video ID.
    """
    if not track_title or not artist_title:
        return ""

    video_id: str = ""
    video_url: str = ""
    driver = None

    try:
        driver = _build_chrome_driver()
        wait = WebDriverWait(driver, 30)

        # ── Step 2: YouTube search ────────────────────────────────────────
        driver.get("https://www.youtube.com/")
        search_box = wait.until(
            EC.presence_of_element_located((By.NAME, "search_query"))
        )
        search_box.send_keys(f"{track_title} {artist_title}")
        search_box.submit()

        # Wait briefly for results to render
        time.sleep(3)

        # ── Step 3: First non‑ad result ───────────────────────────────────
        results = driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer")
        first_result = None
        for result in results:
            if not result.find_elements(By.CSS_SELECTOR, "ytd-ad-slot-renderer"):
                first_result = result
                break

        if first_result:
            title_element = first_result.find_element(By.ID, "video-title")
            video_url_raw = title_element.get_attribute("href") or ""
            LOG.debug("Found YouTube URL: %s", video_url_raw)
            video_url = video_url_raw
            video_id = extract_youtube_video_id(video_url_raw) or ""

    except Exception as exc:
        LOG.debug("Error in populate_youtube_details_for_track: %s", exc)
    finally:
        if driver is not None:
            driver.quit()

    return video_id


def extract_track_metadata(mp3_path: str, youtube_url: str) -> dict:
    """
    Read ID3 tags from the downloaded MP3 and return a metadata dict.
    Falls back to empty strings if a tag is missing.
    """
    metadata = {
        "title": "",
        "artist": "",
        "album": "",
        "genre": "",
        "year": "",
        "duration_seconds": 0,
    }

    path = Path(mp3_path)
    if not path.exists():
        raise FileNotFoundError(f"MP3 file not found: {mp3_path}")

    try:
        audio = MP3(mp3_path)
        metadata["duration_seconds"] = int(audio.info.length)

        tags = ID3(mp3_path)
        metadata["title"] = str(tags.get("TIT2", ""))
        metadata["artist"] = str(tags.get("TPE1", ""))
        metadata["album"] = str(tags.get("TALB", ""))
        metadata["genre"] = str(tags.get("TCON", ""))
        metadata["year"] = str(tags.get("TDRC", ""))
    except Exception as exc:
        LOG.debug("Could not read ID3 tags: %s", exc)

    return metadata


# ---------------------------------------------------------------------------
# yt-dlp download
# ---------------------------------------------------------------------------
def download_youtube_video_as_mp3(
    video_or_id: str,
    output_dir: str,
    progress_callback=None,
) -> str:
    """
    Download a YouTube video as a high-quality MP3 using yt-dlp.

    Args:
        video_or_id:       Either a full YouTube URL or a bare 11-char video ID.
        output_dir:        Directory where the file will be saved.
        progress_callback: Optional callable(line: str) for progress updates.

    Returns:
        Full path to the downloaded MP3 file.
    """
    if not video_or_id:
        raise ValueError("video_or_id must not be empty.")

    if is_valid_youtube_url(video_or_id):
        video_url = video_or_id
        video_id = extract_youtube_video_id(video_or_id) or ""
    else:
        video_id = video_or_id
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    if not video_id:
        raise ValueError(f"Could not determine YouTube video ID from: {video_or_id!r}")

    os.makedirs(output_dir, exist_ok=True)
    # yt-dlp will first download the best audio stream to a temp file,
    # then we convert it to high-quality MP3 using the ffmpeg Python wrapper.
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")

    def _hook(d: dict) -> None:
        if not progress_callback:
            return
        if d.get("status") == "downloading":
            line = (
                f"[download] {d.get('_percent_str', '').strip()} "
                f"of {d.get('_total_bytes_str', '')} "
                f"at {d.get('_speed_str', '')} "
                f"ETA {d.get('_eta_str', '')}"
            )
            LOG.debug(line)
            progress_callback(line)

    ydl_opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "progress_hooks": [_hook],
        "quiet": True,
        "no_warnings": True,
    }

    LOG.debug("Starting yt-dlp download for %s (id=%s)", video_url, video_id)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(video_url, download=True)

    # Determine the downloaded file path from yt-dlp info
    downloaded_ext = result.get("ext", "webm")
    downloaded_path = os.path.join(output_dir, f"{video_id}.{downloaded_ext}")
    mp3_path = os.path.join(output_dir, f"{video_id}.mp3")

    if not os.path.exists(downloaded_path):
        raise FileNotFoundError(
            f"Expected audio file not found after download: {downloaded_path}"
        )

    # Convert to high-quality MP3 using ffmpeg Python wrapper
    LOG.debug("Converting %s to MP3: %s", downloaded_path, mp3_path)
    (
        ffmpeg
        .input(downloaded_path)
        .output(mp3_path, audio_bitrate="320k", acodec="libmp3lame")
        .overwrite_output()
        .run(quiet=True)
    )

    if not os.path.exists(mp3_path):
        raise FileNotFoundError(
            f"Expected MP3 not found after conversion: {mp3_path}"
        )

    # Optionally remove the original downloaded file to save space
    try:
        os.remove(downloaded_path)
    except OSError:
        pass

    LOG.debug("Download and conversion complete: %s", mp3_path)
    return mp3_path

