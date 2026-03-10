from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """
    App-wide configuration (paths only for now).

    Defaults are repo-relative when run from the project root.
    """

    storage_root: Path = Path("storage_data")
    data_root: Path = Path("data")

    @property
    def db_path(self) -> Path:
        return self.data_root / "synciflow.sqlite3"

