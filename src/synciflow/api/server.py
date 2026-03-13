from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
import importlib.resources as resources
import re
import shutil
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select

from synciflow.core.job_manager import (
    complete_job,
    create_job,
    fail_job,
    get_job,
    update_job_progress,
)
from synciflow.core.library_manager import Library
from synciflow.core.notification_bus import (
    ERROR,
    NotificationBus,
    NotificationEvent,
    PLAYLIST_COMPLETED,
    PLAYLIST_PROGRESS,
    SYNC_COMPLETED,
    SYNC_PROGRESS,
    TRACK_DOWNLOAD_COMPLETED,
    TRACK_DOWNLOAD_STARTED,
)
from synciflow.core.utils import LIKES_PLAYLIST_ID
from synciflow.db.database import get_session
from synciflow.db.models import Playlist, PlaylistTrack, Track
from synciflow.storage.zip_builder import build_playlist_zip
from synciflow.services.tagging import ensure_cover_art
from fastapi.middleware.cors import CORSMiddleware


class LoadRequest(BaseModel):
    url: str


@dataclass(frozen=True)
class AppState:
    library: Library


def _find_frontend_dir() -> Optional[Path]:
    """
    Locate the packaged frontend build directory.

    Preference order:
    1. Packaged under the installed `synciflow` package as `synciflow/frontend`.
    2. Repository checkout with `frontend/` at the project root (for development).
    """
    # 1) Packaged inside the synciflow package (recommended for production)
    try:
        base = resources.files("synciflow") / "frontend"
        candidate = Path(base)
        if candidate.is_dir():
            return candidate
    except Exception:
        # Fallbacks are handled below
        pass

    # 2) Development checkout: look for a top-level `frontend/` directory
    here = Path(__file__).resolve()
    project_root_candidates = [
        here.parent.parent.parent,  # src/synciflow/api/server.py -> project root
        here.parent.parent,         # src/synciflow/api -> src/synciflow
    ]
    for root in project_root_candidates:
        candidate = root / "frontend"
        if candidate.is_dir():
            return candidate

    return None


def _run_track_load_job(
    library: Library,
    url: str,
    job_id: str,
    bus: NotificationBus,
) -> None:
    with Session(library.engine) as session:
        try:
            update_job_progress(session, job_id, 0.0, "Starting track download")
            bus.publish_sync(
                NotificationEvent(TRACK_DOWNLOAD_STARTED, job_id=job_id, message="Starting")
            )

            def track_progress(phase: str) -> None:
                with Session(library.engine) as s2:
                    if phase == "started":
                        update_job_progress(s2, job_id, 0.0, "Downloading")
                    else:
                        update_job_progress(s2, job_id, 1.0, "Completed")

            tm = library.track_manager(session)
            track = tm.load_track(url, progress_callback=track_progress)

            complete_job(session, job_id)
            bus.publish_sync(
                NotificationEvent(
                    TRACK_DOWNLOAD_COMPLETED,
                    job_id=job_id,
                    progress=1.0,
                    message=track.track_title or track.track_id,
                    payload={"track_id": track.track_id},
                )
            )
        except Exception as e:
            fail_job(session, job_id, str(e))
            bus.publish_sync(
                NotificationEvent(ERROR, job_id=job_id, message=str(e))
            )
            raise


def _run_playlist_load_job(
    library: Library,
    url: str,
    job_id: str,
    bus: NotificationBus,
) -> None:
    with Session(library.engine) as session:
        try:
            update_job_progress(session, job_id, 0.0, "Loading playlist")

            def progress_cb(current: int, total: int, message: str) -> None:
                with Session(library.engine) as s2:
                    p = current / total if total else 0.0
                    update_job_progress(s2, job_id, p, message)
                bus.publish_sync(
                    NotificationEvent(
                        PLAYLIST_PROGRESS,
                        job_id=job_id,
                        progress=p,
                        message=message,
                        payload={"current": current, "total": total},
                    )
                )

            pm = library.playlist_manager(session)
            playlist = pm.load_playlist(url, progress_callback=progress_cb)

            complete_job(session, job_id)
            bus.publish_sync(
                NotificationEvent(
                    PLAYLIST_COMPLETED,
                    job_id=job_id,
                    progress=1.0,
                    message=playlist.title or playlist.playlist_id,
                    payload={"playlist_id": playlist.playlist_id},
                )
            )
        except Exception as e:
            fail_job(session, job_id, str(e))
            bus.publish_sync(
                NotificationEvent(ERROR, job_id=job_id, message=str(e))
            )
            raise


def _run_likes_load_job(
    library: Library,
    job_id: str,
    bus: NotificationBus,
) -> None:
    with Session(library.engine) as session:
        try:
            update_job_progress(session, job_id, 0.0, "Loading liked songs")

            def progress_cb(current: int, total: int, message: str) -> None:
                with Session(library.engine) as s2:
                    p = current / total if total else 0.0
                    update_job_progress(s2, job_id, p, message)
                bus.publish_sync(
                    NotificationEvent(
                        PLAYLIST_PROGRESS,
                        job_id=job_id,
                        progress=p,
                        message=message,
                        payload={"current": current, "total": total, "playlist_id": LIKES_PLAYLIST_ID},
                    )
                )

            pm = library.playlist_manager(session)
            playlist = pm.load_likes(progress_callback=progress_cb)

            complete_job(session, job_id)
            bus.publish_sync(
                NotificationEvent(
                    PLAYLIST_COMPLETED,
                    job_id=job_id,
                    progress=1.0,
                    message=playlist.title or playlist.playlist_id,
                    payload={"playlist_id": playlist.playlist_id},
                )
            )
        except Exception as e:
            fail_job(session, job_id, str(e))
            bus.publish_sync(
                NotificationEvent(ERROR, job_id=job_id, message=str(e))
            )
            raise


def _run_sync_job(
    library: Library,
    url: str,
    job_id: str,
    bus: NotificationBus,
) -> None:
    with Session(library.engine) as session:
        try:
            update_job_progress(session, job_id, 0.0, "Starting sync")

            def progress_cb(current: int, total: int, message: str) -> None:
                with Session(library.engine) as s2:
                    p = current / total if total else 0.0
                    update_job_progress(s2, job_id, p, message)
                bus.publish_sync(
                    NotificationEvent(
                        SYNC_PROGRESS,
                        job_id=job_id,
                        progress=p,
                        message=message,
                        payload={"current": current, "total": total},
                    )
                )

            sm = library.sync_manager(session)
            result = sm.sync_playlist(url, progress_callback=progress_cb)

            complete_job(session, job_id)
            bus.publish_sync(
                NotificationEvent(
                    SYNC_COMPLETED,
                    job_id=job_id,
                    progress=1.0,
                    message=f"added={result.added} removed={result.removed} kept={result.kept}",
                    payload={
                        "added": result.added,
                        "removed": result.removed,
                        "kept": result.kept,
                    },
                )
            )
        except Exception as e:
            fail_job(session, job_id, str(e))
            bus.publish_sync(
                NotificationEvent(ERROR, job_id=job_id, message=str(e))
            )
            raise


def _run_likes_sync_job(
    library: Library,
    job_id: str,
    bus: NotificationBus,
) -> None:
    with Session(library.engine) as session:
        try:
            update_job_progress(session, job_id, 0.0, "Starting likes sync")

            def progress_cb(current: int, total: int, message: str) -> None:
                with Session(library.engine) as s2:
                    p = current / total if total else 0.0
                    update_job_progress(s2, job_id, p, message)
                bus.publish_sync(
                    NotificationEvent(
                        SYNC_PROGRESS,
                        job_id=job_id,
                        progress=p,
                        message=message,
                        payload={"current": current, "total": total, "playlist_id": LIKES_PLAYLIST_ID},
                    )
                )

            sm = library.sync_manager(session)
            result = sm.sync_likes(progress_callback=progress_cb)

            complete_job(session, job_id)
            bus.publish_sync(
                NotificationEvent(
                    SYNC_COMPLETED,
                    job_id=job_id,
                    progress=1.0,
                    message=f"added={result.added} removed={result.removed} kept={result.kept}",
                    payload={
                        "added": result.added,
                        "removed": result.removed,
                        "kept": result.kept,
                        "playlist_id": LIKES_PLAYLIST_ID,
                    },
                )
            )
        except Exception as e:
            fail_job(session, job_id, str(e))
            bus.publish_sync(
                NotificationEvent(ERROR, job_id=job_id, message=str(e))
            )
            raise


@asynccontextmanager
async def _lifespan(app: FastAPI):
    bus = NotificationBus()
    loop = asyncio.get_running_loop()
    bus.start_bridge(loop)
    app.state.notification_bus = bus
    yield
    bus.stop_bridge()


def create_app(library: Library | None = None) -> FastAPI:
    library = library or Library.create()
    app = FastAPI(title="synciflow", version="0.0.1", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state._synciflow = AppState(library=library)

    def _session():
        yield from get_session(library.engine)

    @app.post("/track/load")
    async def load_track(req: LoadRequest, session: Session = Depends(_session)):
        bus: NotificationBus = app.state.notification_bus
        job = create_job(session, "track_load")
        asyncio.create_task(
            asyncio.to_thread(_run_track_load_job, library, req.url, job.job_id, bus)
        )
        return {"job_id": job.job_id}, 202

    @app.post("/playlist/load")
    async def load_playlist(req: LoadRequest, session: Session = Depends(_session)):
        bus: NotificationBus = app.state.notification_bus
        job = create_job(session, "playlist_load")
        asyncio.create_task(
            asyncio.to_thread(_run_playlist_load_job, library, req.url, job.job_id, bus)
        )
        return {"job_id": job.job_id}, 202

    @app.post("/likes/load")
    async def load_likes(session: Session = Depends(_session)):
        """
        Load Spotify Liked Songs into the library as a pseudo-playlist with ID 'likes'.
        """
        bus: NotificationBus = app.state.notification_bus
        job = create_job(session, "likes_load")
        asyncio.create_task(
            asyncio.to_thread(_run_likes_load_job, library, job.job_id, bus)
        )
        return {"job_id": job.job_id}, 202

    @app.websocket("/ws/notifications")
    async def ws_notifications(websocket: WebSocket):
        await websocket.accept()
        bus: NotificationBus = app.state.notification_bus
        subscriber_queue = bus.subscribe()
        try:
            while True:
                event = await subscriber_queue.get()
                await websocket.send_json(event.to_dict())
        except WebSocketDisconnect:
            pass
        finally:
            bus.unsubscribe(subscriber_queue)

    @app.get("/jobs/{job_id}")
    def get_job_status(job_id: str, session: Session = Depends(_session)):
        job = get_job(session, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }

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
    async def sync_playlist(req: LoadRequest, session: Session = Depends(_session)):
        bus: NotificationBus = app.state.notification_bus
        job = create_job(session, "sync")
        asyncio.create_task(
            asyncio.to_thread(_run_sync_job, library, req.url, job.job_id, bus)
        )
        return {"job_id": job.job_id}, 202

    @app.post("/likes/sync")
    async def sync_likes(session: Session = Depends(_session)):
        """
        Sync the Liked Songs pseudo-playlist (id='likes') against the current Spotify likes set.
        """
        bus: NotificationBus = app.state.notification_bus
        job = create_job(session, "likes_sync")
        asyncio.create_task(
            asyncio.to_thread(_run_likes_sync_job, library, job.job_id, bus)
        )
        return {"job_id": job.job_id}, 202

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

    @app.get("/library/download-all-tracks.zip")
    def download_all_tracks_zip(session: Session = Depends(_session)):
        rows = session.exec(
            select(Track).order_by(Track.created_at, Track.track_id)
        ).all()

        track_files = []
        tmp_root = library.files.storage.tmp_dir / "library-zips" / "all-tracks"
        position = 1
        for track in rows:
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
            track_files.append((position, track.track_id, display_name, tagged_path))
            position += 1

        if not track_files:
            raise HTTPException(status_code=404, detail="No audio files available in library")

        zip_path = build_playlist_zip(library.files, "all-tracks", track_files)
        filename = "all-tracks.zip"
        return FileResponse(path=str(zip_path), media_type="application/zip", filename=filename)

    # --- Frontend static UI (React build) ---
    frontend_dir = _find_frontend_dir()
    if frontend_dir is not None:
        index_file = frontend_dir / "index.html"

        # Serve asset files (JS, CSS, images) from the bundled frontend build.
        assets_dir = frontend_dir / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="frontend-assets",
            )

        @app.get("/", include_in_schema=False)
        async def serve_frontend_root():
            if not index_file.is_file():
                raise HTTPException(status_code=500, detail="Frontend index.html not found")
            return FileResponse(str(index_file), media_type="text/html")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend_spa(full_path: str):
            """
            Serve the React single-page app for non-API routes.

            Rules:
            - If a static asset exists under the frontend directory for the requested path, serve it.
            - Otherwise, fall back to index.html to let the SPA router handle the route.
            This catch-all is defined after API routes so it does not interfere with them.
            """
            # Try direct file match first (e.g. /favicon.ico, /assets/..., etc.)
            candidate = frontend_dir / full_path
            if candidate.is_file():
                # Let FileResponse infer the correct content type.
                return FileResponse(str(candidate))

            if not index_file.is_file():
                raise HTTPException(status_code=500, detail="Frontend index.html not found")
            return FileResponse(str(index_file), media_type="text/html")

    return app

