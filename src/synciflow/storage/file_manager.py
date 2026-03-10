from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .path_manager import StoragePaths, ensure_parent_dir, ensure_storage_dirs, track_audio_path


@dataclass(frozen=True)
class FileManager:
    storage: StoragePaths

    def init_storage(self) -> None:
        ensure_storage_dirs(self.storage)

    def audio_path(self, track_id: str) -> Path:
        return track_audio_path(self.storage, track_id)

    def exists(self, track_id: str) -> bool:
        return self.audio_path(track_id).exists()

    def atomic_move_to_library(self, track_id: str, tmp_mp3_path: str | Path) -> Path:
        """
        Atomically move a downloaded temp file into the library path.

        Notes:
        - Uses os.replace (atomic on same filesystem).
        - Ensures parent directory exists.
        """
        self.init_storage()
        src = Path(tmp_mp3_path)
        if not src.exists():
            raise FileNotFoundError(str(src))

        dst = self.audio_path(track_id)
        ensure_parent_dir(dst)
        os.replace(str(src), str(dst))
        return dst

    def delete(self, track_id: str) -> None:
        path = self.audio_path(track_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def open_for_stream(self, track_id: str, mode: str = "rb"):
        path = self.audio_path(track_id)
        return path.open(mode)

    def copy_into_tmp(self, src_path: str | Path) -> Path:
        """
        Helper for tests/fakes: copy a file into tmp/ and return the new path.
        """
        self.init_storage()
        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(str(src))
        dst = self.storage.tmp_dir / src.name
        ensure_parent_dir(dst)
        shutil.copyfile(str(src), str(dst))
        return dst

