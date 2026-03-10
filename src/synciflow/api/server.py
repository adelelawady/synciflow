from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from synciflow.core.library_manager import Library
from synciflow.db.database import get_session
from synciflow.db.models import Playlist, Track


class LoadRequest(BaseModel):
    url: str


@dataclass(frozen=True)
class AppState:
    library: Library


def create_app(library: Library | None = None) -> FastAPI:
    library = library or Library.create()
    app = FastAPI(title="synciflow", version="0.0.1")
    app.state._synciflow = AppState(library=library)

    def _session():
        yield from get_session(library.engine)

    @app.post("/track/load")
    def load_track(req: LoadRequest, session: Session = Depends(_session)):
        tm = library.track_manager(session)
        track = tm.load_track(req.url)
        return track.model_dump()

    @app.post("/playlist/load")
    def load_playlist(req: LoadRequest, session: Session = Depends(_session)):
        pm = library.playlist_manager(session)
        playlist = pm.load_playlist(req.url)
        return playlist.model_dump()

    @app.post("/playlist/sync")
    def sync_playlist(req: LoadRequest, session: Session = Depends(_session)):
        sm = library.sync_manager(session)
        result = sm.sync_playlist(req.url)
        return {"added": result.added, "removed": result.removed, "kept": result.kept}

    @app.get("/track/{track_id}")
    def get_track(track_id: str, session: Session = Depends(_session)):
        t = session.exec(select(Track).where(Track.track_id == track_id)).first()
        if t is None:
            raise HTTPException(status_code=404, detail="Track not found")
        return t.model_dump()

    @app.get("/playlist/{playlist_id}")
    def get_playlist(playlist_id: str, session: Session = Depends(_session)):
        p = session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
        if p is None:
            raise HTTPException(status_code=404, detail="Playlist not found")
        return p.model_dump()

    @app.get("/track/{track_id}/stream")
    def stream_track(track_id: str, session: Session = Depends(_session)):
        t = session.exec(select(Track).where(Track.track_id == track_id)).first()
        if t is None:
            raise HTTPException(status_code=404, detail="Track not found")
        if not t.audio_path:
            raise HTTPException(status_code=404, detail="Audio not available")
        return FileResponse(path=t.audio_path, media_type="audio/mpeg", filename=f"{track_id}.mp3")

    return app

