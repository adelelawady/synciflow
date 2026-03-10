from __future__ import annotations

import uuid
import zipfile
from pathlib import Path
from typing import Iterable, Tuple

from .file_manager import FileManager
from .path_manager import ensure_parent_dir


def build_playlist_zip(
    files: FileManager,
    playlist_id: str,
    track_files: Iterable[Tuple[int, str, str, Path]],
) -> Path:
    """
    Build a ZIP file for the given playlist_id containing the provided track files.

    track_files is an iterable of (position, track_id, display_name, audio_path).
    `display_name` should be a sanitized base filename without extension.
    The ZIP is written into a unique temp file and the final path is returned.
    """
    zip_path = files.storage.tmp_dir / "zips" / f"{playlist_id}-{uuid.uuid4().hex}.zip"
    ensure_parent_dir(zip_path)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for position, track_id, display_name, audio_path in track_files:
            if not audio_path.exists():
                continue
            suffix = audio_path.suffix or ".mp3"
            arcname = f"{position:03d}-{display_name}{suffix}"
            zf.write(str(audio_path), arcname)

    return zip_path

