from __future__ import annotations

import re


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

