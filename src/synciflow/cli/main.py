from __future__ import annotations

import shutil
from pathlib import Path

import typer
from sqlmodel import select

from synciflow.api.server import create_app
from synciflow.config import AppConfig
from synciflow.core.library_manager import Library
from synciflow.core.utils import track_display_name
from synciflow.db.models import Playlist, PlaylistTrack, Track
from synciflow.services.tagging import ensure_cover_art
from synciflow.storage.path_manager import ensure_parent_dir
from synciflow.storage.zip_builder import build_playlist_zip

from .smart import run as run_smart_cli


app = typer.Typer(add_completion=False)


@app.command()
def track(url: str):
    """Load a single track into the offline library."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        tm = lib.track_manager(session)
        t = tm.load_track(url)
        typer.echo(f"{t.track_title} - {t.artist_title}")
        typer.echo(f"id={t.track_id}")
        typer.echo(f"path={t.audio_path}")


@app.command("track-local")
def track_local(track_id: str):
    """Register or repair a track from an existing local file by ID."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        tm = lib.track_manager(session)
        t = tm.load_local(track_id)
        typer.echo(f"{t.track_title or '<unknown title>'} - {t.artist_title or '<unknown artist>'}")
        typer.echo(f"id={t.track_id}")
        typer.echo(f"path={t.audio_path}")


@app.command()
def playlist(url: str):
    """Load a playlist into the offline library (downloads all tracks)."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        pm = lib.playlist_manager(session)
        p = pm.load_playlist(url)
        typer.echo(f"{p.title}")
        typer.echo(f"id={p.playlist_id}")


@app.command("playlist-local")
def playlist_local(playlist_id: str):
    """Register or repair a playlist using local tracks and stored metadata."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        pm = lib.playlist_manager(session)
        p = pm.load_local(playlist_id)
        typer.echo(f"{p.title or '<untitled playlist>'}")
        typer.echo(f"id={p.playlist_id}")


@app.command()
def sync(url: str):
    """Sync an offline playlist with the current Spotify playlist state."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        sm = lib.sync_manager(session)
        r = sm.sync_playlist(url)
        typer.echo(f"added={r.added} removed={r.removed} kept={r.kept}")


@app.command("tracks")
def list_tracks():
    """List all tracks in the library."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        tracks = session.exec(select(Track)).all()
        if not tracks:
            typer.echo("No tracks found.")
            return
        for t in tracks:
            typer.echo(f"{t.track_id} | {t.track_title} - {t.artist_title}")


@app.command("playlists")
def list_playlists():
    """List all playlists in the library."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        playlists = session.exec(select(Playlist)).all()
        if not playlists:
            typer.echo("No playlists found.")
            return
        for p in playlists:
            typer.echo(f"{p.playlist_id} | {p.title}")


def _build_playlist_zip_with_cover(lib: Library, playlist_id: str) -> Path:
    """Build a ZIP for the playlist with display names and embedded cover art. Returns path to the zip file."""
    with lib.session() as session:
        rows = session.exec(
            select(PlaylistTrack, Track)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .where(PlaylistTrack.track_id == Track.track_id)
            .order_by(PlaylistTrack.position)
        ).all()

    track_files = []
    tmp_root = lib.files.storage.tmp_dir / "playlist-zips" / playlist_id
    for rel, track in rows:
        if not track.audio_path:
            continue
        source_audio_path = Path(track.audio_path)
        if not source_audio_path.exists():
            continue
        tmp_audio_dir = tmp_root / "tracks"
        tmp_audio_dir.mkdir(parents=True, exist_ok=True)
        tmp_audio_path = tmp_audio_dir / f"{track.track_id}.mp3"
        try:
            shutil.copyfile(source_audio_path, tmp_audio_path)
        except OSError:
            continue
        tagged_path = ensure_cover_art(tmp_audio_path, track.track_image_url)
        display_name = track_display_name(track)
        track_files.append((rel.position, track.track_id, display_name, tagged_path))

    if not track_files:
        typer.echo("No audio files available for this playlist.", err=True)
        raise typer.Exit(code=1)
    return build_playlist_zip(lib.files, playlist_id, track_files)


@app.command("download-track")
def download_track(track_id: str, out: Path | None = typer.Argument(None)):
    """
    Download or export a single track file by ID.

    - If --out is omitted, prints the existing local path.
    - If --out is a directory, writes into that directory.
    - If --out is a file path, writes exactly to that path.
    """
    lib = Library.create(AppConfig())
    with lib.session() as session:
        t = session.exec(select(Track).where(Track.track_id == track_id)).first()
        if t is None:
            typer.echo("Track not found.", err=True)
            raise typer.Exit(code=1)
        if not t.audio_path:
            typer.echo("Track has no audio file.", err=True)
            raise typer.Exit(code=1)

        src = Path(t.audio_path)
        if not src.exists():
            typer.echo("Audio file is missing on disk.", err=True)
            raise typer.Exit(code=1)

        if out is None:
            typer.echo(str(src))
            return

        out = Path(out)
        if out.is_dir():
            dest = out / src.name
        else:
            dest = out
        ensure_parent_dir(dest)
        shutil.copyfile(src, dest)
        typer.echo(f"Saved to {dest}")


@app.command("save-track")
def save_track(
    track_id: str,
    out: Path = typer.Argument(..., help="Output file or directory path"),
):
    """
    Save a single track to a file. Uses 'Title - Artist.mp3' when output is a directory.
    """
    lib = Library.create(AppConfig())
    with lib.session() as session:
        t = session.exec(select(Track).where(Track.track_id == track_id)).first()
        if t is None:
            typer.echo("Track not found.", err=True)
            raise typer.Exit(code=1)
        if not t.audio_path:
            typer.echo("Track has no audio file.", err=True)
            raise typer.Exit(code=1)

    src = Path(t.audio_path)
    if not src.exists():
        typer.echo("Audio file is missing on disk.", err=True)
        raise typer.Exit(code=1)

    out = Path(out)
    if out.is_dir():
        dest = out / f"{track_display_name(t)}.mp3"
    else:
        dest = out
    ensure_parent_dir(dest)
    shutil.copyfile(src, dest)
    typer.echo(f"Saved to {dest}")


@app.command("download-playlist-zip")
def download_playlist_zip(playlist_id: str, out: Path):
    """
    Build a ZIP file for a playlist (with cover art) and save it to the given path.
    """
    lib = Library.create(AppConfig())
    zip_path = _build_playlist_zip_with_cover(lib, playlist_id)
    out = Path(out)
    if out.is_dir():
        dest = out / zip_path.name
    else:
        dest = out
    ensure_parent_dir(dest)
    shutil.copyfile(zip_path, dest)
    typer.echo(f"Saved ZIP to {dest}")


@app.command("save-playlist")
def save_playlist(
    playlist_id: str,
    out: Path = typer.Argument(..., help="Output ZIP file or directory path"),
):
    """
    Save a playlist as a ZIP file (tracks named 'Title - Artist.mp3', with embedded cover art).
    """
    lib = Library.create(AppConfig())
    with lib.session() as session:
        playlist = session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
        if playlist is None:
            typer.echo("Playlist not found.", err=True)
            raise typer.Exit(code=1)

    zip_path = _build_playlist_zip_with_cover(lib, playlist_id)
    out = Path(out)
    if out.is_dir():
        dest = out / f"{playlist.title or playlist_id}.zip"
    else:
        dest = out
    ensure_parent_dir(dest)
    shutil.copyfile(zip_path, dest)
    typer.echo(f"Saved playlist ZIP to {dest}")


@app.command()
def smart():
    """Launch the interactive smart CLI."""
    run_smart_cli()


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn

    api = create_app(Library.create(AppConfig()))
    uvicorn.run(api, host=host, port=port)


def run():
    app()
