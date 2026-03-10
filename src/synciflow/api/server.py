from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from synciflow.core.library_manager import Library
from synciflow.db.database import get_session
from synciflow.db.models import Playlist, PlaylistTrack, Track
from synciflow.storage.zip_builder import build_playlist_zip
from synciflow.services.tagging import ensure_cover_art


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

    @app.post("/track/{track_id}/load_local")
    def load_track_local(track_id: str, session: Session = Depends(_session)):
        tm = library.track_manager(session)
        track = tm.load_local(track_id)
        return track.model_dump()

    @app.post("/playlist/{playlist_id}/load_local")
    def load_playlist_local(playlist_id: str, session: Session = Depends(_session)):
        pm = library.playlist_manager(session)
        playlist = pm.load_local(playlist_id)
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

    @app.get("/tracks")
    def list_tracks(session: Session = Depends(_session)):
        tracks = session.exec(select(Track)).all()
        return [t.model_dump() for t in tracks]

    @app.get("/playlists")
    def list_playlists(session: Session = Depends(_session)):
        playlists = session.exec(select(Playlist)).all()
        return [p.model_dump() for p in playlists]

    @app.get("/playlist/{playlist_id}/tracks")
    def get_playlist_tracks(playlist_id: str, session: Session = Depends(_session)):
        rows = session.exec(
            select(PlaylistTrack, Track)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .where(PlaylistTrack.track_id == Track.track_id)
            .order_by(PlaylistTrack.position)
        ).all()
        if not rows:
            raise HTTPException(status_code=404, detail="Playlist not found or has no tracks")
        return [
            {
                "position": rel.position,
                "track": track.model_dump(),
            }
            for rel, track in rows
        ]

    @app.get("/track/{track_id}/stream")
    def stream_track(track_id: str, session: Session = Depends(_session)):
        t = session.exec(select(Track).where(Track.track_id == track_id)).first()
        if t is None:
            raise HTTPException(status_code=404, detail="Track not found")
        if not t.audio_path:
            raise HTTPException(status_code=404, detail="Audio not available")
        return FileResponse(path=t.audio_path, media_type="audio/mpeg", filename=f"{track_id}.mp3")

    @app.get("/track/{track_id}/download")
    def download_track(track_id: str, session: Session = Depends(_session)):
        t = session.exec(select(Track).where(Track.track_id == track_id)).first()
        if t is None:
            raise HTTPException(status_code=404, detail="Track not found")
        if not t.audio_path:
            raise HTTPException(status_code=404, detail="Audio not available")
        filename = f"{t.track_title or track_id}.mp3"
        return FileResponse(path=t.audio_path, media_type="audio/mpeg", filename=filename)

    def _sanitize_filename(name: str, fallback: str) -> str:
        """
        Sanitize a filename component so it is safe across platforms.
        """
        name = name.strip() or fallback
        # Replace invalid characters with a hyphen.
        name = re.sub(r'[\\\\/:*?"<>|]', "-", name)
        # Collapse repeated whitespace and dashes.
        name = re.sub(r"\\s+", " ", name)
        name = re.sub(r"-{2,}", "-", name)
        # Limit length to a reasonable size.
        return name[:120].strip()

    def _track_display_name(track: Track) -> str:
        parts: list[str] = []
        if track.track_title:
            parts.append(track.track_title)
        if track.artist_title:
            parts.append(track.artist_title)
        base = " - ".join(parts) if parts else track.track_id
        return _sanitize_filename(base, track.track_id)

    @app.get("/playlist/{playlist_id}/download.zip")
    def download_playlist_zip(playlist_id: str, session: Session = Depends(_session)):
        playlist = session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
        if playlist is None:
            raise HTTPException(status_code=404, detail="Playlist not found")

        rows = session.exec(
            select(PlaylistTrack, Track)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .where(PlaylistTrack.track_id == Track.track_id)
            .order_by(PlaylistTrack.position)
        ).all()
        track_files = []
        tmp_root = library.files.storage.tmp_dir / "playlist-zips" / playlist_id
        for rel, track in rows:
            if not track.audio_path:
                continue
            source_audio_path = Path(track.audio_path)
            if not source_audio_path.exists():
                continue

            display_name = _track_display_name(track)

            # Work on a temp copy so we do not mutate the library file.
            tmp_audio_dir = tmp_root / "tracks"
            tmp_audio_dir.mkdir(parents=True, exist_ok=True)
            tmp_audio_path = tmp_audio_dir / f"{track.track_id}.mp3"
            try:
                shutil.copyfile(source_audio_path, tmp_audio_path)
            except OSError:
                continue

            tagged_path = ensure_cover_art(tmp_audio_path, track.track_image_url)
            track_files.append((rel.position, track.track_id, display_name, tagged_path))

        if not track_files:
            raise HTTPException(status_code=404, detail="No audio files available for playlist")

        zip_path = build_playlist_zip(library.files, playlist_id, track_files)
        filename = f"{playlist.title or playlist_id}.zip"
        return FileResponse(path=str(zip_path), media_type="application/zip", filename=filename)

    return app

