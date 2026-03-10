from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import List

from .path_manager import StoragePaths, ensure_parent_dir, playlist_metadata_path


@dataclass
class PlaylistMetadata:
    playlist_id: str
    title: str = ""
    track_ids: List[str] = field(default_factory=list)


def write_playlist_metadata(storage: StoragePaths, metadata: PlaylistMetadata) -> None:
    """
    Persist playlist metadata to a JSON file under storage.playlists_dir.
    """
    path = playlist_metadata_path(storage, metadata.playlist_id)
    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(metadata), f, ensure_ascii=False, indent=2)


def read_playlist_metadata(storage: StoragePaths, playlist_id: str) -> PlaylistMetadata | None:
    """
    Load playlist metadata if it exists; otherwise return None.
    """
    path = playlist_metadata_path(storage, playlist_id)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return PlaylistMetadata(
        playlist_id=data.get("playlist_id", playlist_id),
        title=data.get("title", "") or "",
        track_ids=list(data.get("track_ids") or []),
    )

