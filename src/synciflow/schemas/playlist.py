from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class PlaylistDetails:
    """Holds the result of a playlist scrape."""

    # Use empty defaults so missing data is represented by empty fields.
    playlist_url: str = ""
    playlist_id: str = ""
    title: str = ""
    playlist_image_url: str = ""
    track_urls: List[str] = field(default_factory=list)

