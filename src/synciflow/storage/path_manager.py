from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    @property
    def tracks_dir(self) -> Path:
        return self.root / "tracks"

    @property
    def tmp_dir(self) -> Path:
        return self.root / "tmp"

    @property
    def playlists_dir(self) -> Path:
        return self.root / "playlists"


def track_prefix(track_id: str) -> str:
    return (track_id or "")[:2] or "xx"


def track_audio_path(storage: StoragePaths, track_id: str, ext: str = "mp3") -> Path:
    prefix = track_prefix(track_id)
    return storage.tracks_dir / prefix / f"{track_id}.{ext}"


def playlist_metadata_path(storage: StoragePaths, playlist_id: str) -> Path:
    return storage.playlists_dir / f"{playlist_id}.json"


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_storage_dirs(storage: StoragePaths) -> None:
    storage.root.mkdir(parents=True, exist_ok=True)
    storage.tracks_dir.mkdir(parents=True, exist_ok=True)
    storage.tmp_dir.mkdir(parents=True, exist_ok=True)
    storage.playlists_dir.mkdir(parents=True, exist_ok=True)

