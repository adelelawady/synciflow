from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from synciflow.config import AppConfig
from synciflow.db.database import DatabaseConfig, create_sqlite_engine, init_db
from synciflow.storage.file_manager import FileManager
from synciflow.storage.path_manager import StoragePaths

from .playlist_manager import PlaylistManager
from .sync_manager import SyncManager
from .track_manager import TrackManager


@dataclass(frozen=True)
class Library:
    cfg: AppConfig
    engine: object
    files: FileManager

    @classmethod
    def create(cls, cfg: AppConfig | None = None) -> "Library":
        cfg = cfg or AppConfig()
        engine = create_sqlite_engine(DatabaseConfig(db_path=cfg.db_path))
        init_db(engine)
        files = FileManager(StoragePaths(root=cfg.storage_root))
        files.init_storage()
        return cls(cfg=cfg, engine=engine, files=files)

    def session(self) -> Session:
        return Session(self.engine)

    def track_manager(self, session: Session) -> TrackManager:
        return TrackManager(session=session, files=self.files)

    def playlist_manager(self, session: Session) -> PlaylistManager:
        tm = self.track_manager(session)
        return PlaylistManager(session=session, tracks=tm, files=self.files)

    def sync_manager(self, session: Session) -> SyncManager:
        tm = self.track_manager(session)
        return SyncManager(session=session, tracks=tm)

