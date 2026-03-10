from __future__ import annotations

import typer

from synciflow.api.server import create_app
from synciflow.config import AppConfig
from synciflow.core.library_manager import Library


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


@app.command()
def playlist(url: str):
    """Load a playlist into the offline library (downloads all tracks)."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        pm = lib.playlist_manager(session)
        p = pm.load_playlist(url)
        typer.echo(f"{p.title}")
        typer.echo(f"id={p.playlist_id}")


@app.command()
def sync(url: str):
    """Sync an offline playlist with the current Spotify playlist state."""
    lib = Library.create(AppConfig())
    with lib.session() as session:
        sm = lib.sync_manager(session)
        r = sm.sync_playlist(url)
        typer.echo(f"added={r.added} removed={r.removed} kept={r.kept}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn

    api = create_app(Library.create(AppConfig()))
    uvicorn.run(api, host=host, port=port)


def run():
    app()

