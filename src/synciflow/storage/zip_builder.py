from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Iterable, Tuple

from .file_manager import FileManager
from .path_manager import ensure_parent_dir


def build_playlist_zip(
    files: FileManager,
    playlist_id: str,
    track_files: Iterable[Tuple[int, str, Path]],
) -> Path:
    """
    Build a ZIP file for the given playlist_id containing the provided track files.

    track_files is an iterable of (position, track_id, audio_path).
    The ZIP is written into the storage tmp/ directory and the final path is returned.
    """
    zip_path = files.storage.tmp_dir / f"{playlist_id}.zip"
    ensure_parent_dir(zip_path)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for position, track_id, audio_path in track_files:
            if not audio_path.exists():
                continue
            suffix = audio_path.suffix or ".mp3"
            arcname = f"{position:03d}-{track_id}{suffix}"
            zf.write(str(audio_path), arcname)

    return zip_path

