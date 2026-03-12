from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Track(SQLModel, table=True):
    track_id: str = Field(primary_key=True)
    spotify_url: str = ""
    track_title: str = ""
    artist_title: str = ""
    track_image_url: str = ""
    audio_path: str = ""

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    downloaded_at: Optional[datetime] = Field(default=None, nullable=True)


class Playlist(SQLModel, table=True):
    playlist_id: str = Field(primary_key=True)
    playlist_url: str = ""
    title: str = ""
    playlist_image_url: str = ""

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    last_synced_at: Optional[datetime] = Field(default=None, nullable=True)


class PlaylistTrack(SQLModel, table=True):
    playlist_id: str = Field(primary_key=True, foreign_key="playlist.playlist_id")
    track_id: str = Field(primary_key=True, foreign_key="track.track_id")
    position: int = Field(default=0, nullable=False)


class Job(SQLModel, table=True):
    job_id: str = Field(primary_key=True)
    job_type: str = Field(default="", nullable=False)
    status: str = Field(default="pending", nullable=False)
    progress: float = Field(default=0.0, nullable=False)
    message: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

