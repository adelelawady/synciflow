"""
YouTube resolution + download helpers.

This module is copied/refactored from the previous test-only location
`tests/synciflow/core/youtube.py` so it can be used by the real library code.

Selenium / webdriver dependency has been removed entirely.
YouTube search is now performed via YouTube's internal InnerTube API
(the same JSON endpoint the web app uses), which requires no API key,
no browser, and is significantly faster.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

import ffmpeg
import requests
import yt_dlp
from mutagen.id3 import ID3
from mutagen.mp3 import MP3

LOG = logging.getLogger("synciflow.youtube")

# ---------------------------------------------------------------------------
# InnerTube constants – these are the same values the YouTube web client sends.
# They are publicly visible in every browser request to youtube.com and do not
# constitute private credentials.
# ---------------------------------------------------------------------------
_INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
_INNERTUBE_URL = (
    "https://www.youtube.com/youtubei/v1/search"
    f"?key={_INNERTUBE_API_KEY}&prettyPrint=false"
)
_INNERTUBE_CONTEXT = {
    "client": {
        "clientName": "WEB",
        "clientVersion": "2.20240101.00.00",
        "hl": "en",
        "gl": "US",
    }
}
_REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.youtube.com",
    "Referer": "https://www.youtube.com/",
}


# ---------------------------------------------------------------------------
# URL / ID helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# YouTube search via InnerTube (no Selenium, no API key)
# ---------------------------------------------------------------------------

def _innertube_search(query: str, max_retries: int = 3) -> list[dict]:
    """
    Call YouTube's internal InnerTube search endpoint and return a flat list
    of video renderer dicts from the first page of results.

    Each dict contains at minimum ``videoId`` and ``title.runs[].text``.
    Returns an empty list on any error.
    """
    payload = {
        "context": _INNERTUBE_CONTEXT,
        "query": query,
        "params": "EgIQAQ%3D%3D",  # filter: videos only
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                _INNERTUBE_URL,
                headers=_REQUEST_HEADERS,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            LOG.debug("InnerTube search attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt == max_retries:
                return []
            time.sleep(1.5 * attempt)

    # Walk the deeply-nested response and collect videoRenderer objects.
    videos: list[dict] = []
    try:
        sections = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        for section in sections:
            items = (
                section.get("itemSectionRenderer", {})
                .get("contents", [])
            )
            for item in items:
                vr = item.get("videoRenderer")
                if vr and vr.get("videoId"):
                    videos.append(vr)
    except Exception as exc:
        LOG.debug("Failed to parse InnerTube response: %s", exc)

    return videos


def populate_youtube_details_for_track(track_title: str, artist_title: str) -> str:
    """
    Search YouTube for *track_title* by *artist_title* and return the first
    matching video ID.

    Uses YouTube's InnerTube API directly — no browser, no Selenium, no API key
    required.  Returns an empty string if no result is found or on any error.
    """
    if not track_title or not artist_title:
        return ""

    query = f"{track_title} {artist_title}"
    LOG.debug("Searching YouTube (InnerTube) for: %r", query)

    videos = _innertube_search(query)
    if not videos:
        LOG.debug("No YouTube results found for query: %r", query)
        return ""

    video_id: str = videos[0].get("videoId", "")
    LOG.debug("First YouTube result: videoId=%r", video_id)
    return video_id


# ---------------------------------------------------------------------------
# MP3 metadata helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

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
        raise FileNotFoundError(
            f"Expected audio file not found after download: {downloaded_path}"
        )

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