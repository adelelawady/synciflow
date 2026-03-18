from __future__ import annotations

from dataclasses import dataclass, field


def _ms_to_duration_str(ms: int) -> str:
    """Convert milliseconds to a human-readable string like '3:29'."""
    if ms <= 0:
        return "0:00"
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


@dataclass
class TrackDetails:
    spotify_url: str = ""
    track_id: str = ""
    track_title: str = ""
    artist_title: str = ""
    track_image_url: str = ""
    duration_ms: int = 0
    duration_str: str = ""