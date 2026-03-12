from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from synciflow.schemas.track import TrackDetails
from synciflow.storage.file_manager import FileManager

from .youtube import download_youtube_video_as_mp3, populate_youtube_details_for_track


class DownloadError(RuntimeError):
    """
    Raised when a track cannot be downloaded (for example, when a YouTube
    video ID cannot be resolved for the given Spotify track metadata).
    """


@dataclass(frozen=True)
class DownloadResult:
    youtube_video_id: str
    tmp_mp3_path: Path


def download_track_to_tmp(details: TrackDetails, file_manager: FileManager) -> DownloadResult:
    """
    Resolve a track to a YouTube video and download it into storage tmp/.

    Returns a temp mp3 path. Caller is responsible for atomically moving it into
    the final library location.
    """
    file_manager.init_storage()
    youtube_video_id = populate_youtube_details_for_track(details.track_title, details.artist_title)
    if not youtube_video_id:
        raise DownloadError("Could not resolve YouTube video ID for track.")

    # Download into tmp dir; yt-dlp will name it {video_id}.mp3.
    tmp_dir = str(file_manager.storage.tmp_dir)
    tmp_mp3 = Path(download_youtube_video_as_mp3(youtube_video_id, tmp_dir))

    # If a filename collision happens, move aside with a UUID name.
    if tmp_mp3.exists() and tmp_mp3.name != f"{youtube_video_id}.mp3":
        return DownloadResult(youtube_video_id=youtube_video_id, tmp_mp3_path=tmp_mp3)

    if tmp_mp3.exists():
        unique = file_manager.storage.tmp_dir / f"{youtube_video_id}-{uuid.uuid4().hex}.mp3"
        tmp_mp3.rename(unique)
        tmp_mp3 = unique

    return DownloadResult(youtube_video_id=youtube_video_id, tmp_mp3_path=tmp_mp3)

