from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    return create_engine(
        cfg.url,
        echo=False,
        connect_args={"check_same_thread": False},
    )


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

