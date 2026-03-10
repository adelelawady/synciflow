from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrackDetails:
    """
    Holds all gathered information for a single Spotify track.

    All string fields default to the empty string so that missing data is represented
    as empty fields instead of None.
    """

    spotify_url: str = ""
    track_id: str = ""
    track_title: str = ""
    artist_title: str = ""
    track_image_url: str = ""

