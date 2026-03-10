"""
YouTube resolution + download helpers.

This module is copied/refactored from the previous test-only location
`tests/synciflow/core/youtube.py` so it can be used by the real library code.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import ffmpeg
import yt_dlp
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

LOG = logging.getLogger("synciflow.youtube")


def is_valid_youtube_url(url: str) -> bool:
    pattern = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/")
    return bool(pattern.search(url or ""))


def extract_youtube_video_id(url: str) -> str | None:
    if not url:
        return None
    match = re.search(r"v=([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    return None


def _build_chrome_driver() -> webdriver.Chrome:
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


def populate_youtube_details_for_track(track_title: str, artist_title: str) -> str:
    """
    Perform a YouTube search and return the first video ID.
    """
    if not track_title or not artist_title:
        return ""

    video_id: str = ""
    driver = None

    try:
        driver = _build_chrome_driver()
        wait = WebDriverWait(driver, 30)

        driver.get("https://www.youtube.com/")
        search_box = wait.until(EC.presence_of_element_located((By.NAME, "search_query")))
        search_box.send_keys(f"{track_title} {artist_title}")
        search_box.submit()
        time.sleep(3)

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
            video_id = extract_youtube_video_id(video_url_raw) or ""

    except Exception as exc:
        LOG.debug("Error populating YouTube details: %s", exc)
    finally:
        if driver is not None:
            driver.quit()

    return video_id


def extract_track_metadata(mp3_path: str, youtube_url: str = "") -> dict:
    metadata = {
        "title": "",
        "artist": "",
        "album": "",
        "genre": "",
        "year": "",
        "duration_seconds": 0,
        "youtube_url": youtube_url or "",
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


def download_youtube_video_as_mp3(
    video_or_id: str,
    output_dir: str,
    progress_callback=None,
) -> str:
    """
    Download a YouTube video as a high-quality MP3 using yt-dlp.
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

    downloaded_ext = result.get("ext", "webm")
    downloaded_path = os.path.join(output_dir, f"{video_id}.{downloaded_ext}")
    mp3_path = os.path.join(output_dir, f"{video_id}.mp3")

    if not os.path.exists(downloaded_path):
        raise FileNotFoundError(f"Expected audio file not found after download: {downloaded_path}")

    LOG.debug("Converting %s to MP3: %s", downloaded_path, mp3_path)
    (
        ffmpeg.input(downloaded_path)
        .output(mp3_path, audio_bitrate="320k", acodec="libmp3lame")
        .overwrite_output()
        .run(quiet=True)
    )

    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"Expected MP3 not found after conversion: {mp3_path}")

    try:
        os.remove(downloaded_path)
    except OSError:
        pass

    LOG.debug("Download and conversion complete: %s", mp3_path)
    return mp3_path

