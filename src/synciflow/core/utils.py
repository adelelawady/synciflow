from __future__ import annotations

import re

from synciflow.db.models import Track

# Stable pseudo-playlist identifier for Spotify Liked Songs.
LIKES_PLAYLIST_ID = "likes"

_SPOTIFY_ID_RE = re.compile(r"/(track|playlist)/([A-Za-z0-9]+)")


def extract_spotify_id(url: str, kind: str) -> str:
    """
    Extract a Spotify object ID from a URL.

    kind: "track" or "playlist"
    """
    if not url:
        return ""
    m = _SPOTIFY_ID_RE.search(url)
    if not m:
        return ""
    found_kind, obj_id = m.group(1), m.group(2)
    if found_kind != kind:
        return ""
    return obj_id


def sanitize_filename(name: str, fallback: str = "unknown") -> str:
    """
    Sanitize a string for use as a filename component (safe across Windows/macOS/Linux).
    """
    name = (name or "").strip() or fallback
    name = re.sub(r'[\\/:*?"<>|]', "-", name)
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"-{2,}", "-", name)
    return name[:120].strip() or fallback


def track_display_name(track: Track) -> str:
    """Build a display filename base from track (e.g. 'Title - Artist') without extension."""
    parts: list[str] = []
    if track.track_title:
        parts.append(track.track_title)
    if track.artist_title:
        parts.append(track.artist_title)
    base = " - ".join(parts) if parts else track.track_id
    return sanitize_filename(base, track.track_id)

