from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine


@dataclass(frozen=True)
class DatabaseConfig:
    db_path: Path

    @property
    def url(self) -> str:
        # Windows paths need 3 slashes for sqlite+pysqlite
        return f"sqlite:///{self.db_path.as_posix()}"


def create_sqlite_engine(cfg: DatabaseConfig):
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        cfg.url,
        echo=False,
        # timeout: seconds to wait for SQLite file lock
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    # Improve concurrency: WAL allows readers during writes, and busy_timeout reduces lock errors.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
        finally:
            cursor.close()
    return engine


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)


def session_scope(engine):
    return Session(engine)


def get_session(engine):
    """
    FastAPI-friendly generator dependency.
    """
    with Session(engine) as session:
        yield session

