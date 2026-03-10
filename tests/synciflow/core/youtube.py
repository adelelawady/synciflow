"""Compatibility re-export for older imports used in tests/scripts.

Real implementation lives in `synciflow.services.youtube`.
"""

from __future__ import annotations

from synciflow.services.youtube import (  # noqa: F401
    download_youtube_video_as_mp3,
    extract_track_metadata,
    extract_youtube_video_id,
    is_valid_youtube_url,
    populate_youtube_details_for_track,
)

