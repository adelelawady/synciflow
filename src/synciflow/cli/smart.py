from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from sqlmodel import delete, select

from synciflow import __version__ as SYNCIFLOW_VERSION
from synciflow.config import AppConfig
from synciflow.core.library_manager import Library
from synciflow.db.models import Playlist, PlaylistTrack, Track


console = Console()


def _print_header() -> None:

    title_lines = [
        "[bold cyan]",
        "  ____                        _  __ _ _                 ",
        " / ___| _   _ _ __   ___ ___ (_)/ _(_) | _____      __  ",
        " \\___ \\| | | | '_ \\ / __/ _ \\| | |_| | |/ _ \\ \\ /\\ / /  ",
        "  ___) | |_| | | | | (_| (_) | |  _| | | (_) \\ V  V /   ",
        " |____/ \\__, |_| |_|\\___\\___/|_|_| |_|_|\\___/ \\_/\\_/    ",
        "        |___/                                           ",
    "[/bold cyan]",
    "",
    "[dim]offline SYNCIFLOW sync • CLI • API[/dim]",
    f"[dim]author: AdelElawady • version: {SYNCIFLOW_VERSION}[/dim]",
    ]
    console.print(Panel("\n".join(title_lines), expand=False))


def _select_main_action() -> str:
    console.print("")
    console.print("[bold]Main menu[/bold]")
    console.print("  [cyan]1[/cyan] Load track by Spotify URL")
    console.print("  [cyan]2[/cyan] Load track by ID (local)")
    console.print("  [cyan]3[/cyan] Load playlist by Spotify URL")
    console.print("  [cyan]4[/cyan] Load playlist by Spotify playlist ID")
    console.print("  [cyan]5[/cyan] List tracks")
    console.print("  [cyan]6[/cyan] List playlists")
    console.print("  [cyan]7[/cyan] Quit")
    return Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")


def _load_track_by_url(lib: Library) -> None:
    from synciflow.core.track_manager import TrackManager  # local import for clarity

    url = Prompt.ask("Spotify track URL")
    with lib.session() as session:
        tm: TrackManager = lib.track_manager(session)
        track = tm.load_track(url)
        console.print(
            Panel(
                f"[bold]{track.track_title or '<untitled>'}[/bold]\n"
                f"[magenta]{track.artist_title}[/magenta]\n\n"
                f"[dim]id[/dim] {track.track_id}\n"
                f"[dim]path[/dim] {track.audio_path}",
                title="Track loaded",
                expand=False,
            )
        )


def _load_track_by_id_local(lib: Library) -> None:
    from synciflow.core.track_manager import TrackManager  # local import for clarity

    track_id = Prompt.ask("Track ID")
    with lib.session() as session:
        tm: TrackManager = lib.track_manager(session)
        try:
            track = tm.load_local(track_id)
        except Exception as exc:  # surface any local-not-found issue
            console.print(f"[red]Error:[/red] {exc}")
            return

        console.print(
            Panel(
                f"[bold]{track.track_title or '<untitled>'}[/bold]\n"
                f"[magenta]{track.artist_title}[/magenta]\n\n"
                f"[dim]id[/dim] {track.track_id}\n"
                f"[dim]path[/dim] {track.audio_path}",
                title="Local track",
                expand=False,
            )
        )


def _load_playlist_by_url(lib: Library) -> None:
    from synciflow.core.playlist_manager import PlaylistManager  # local import for clarity

    url = Prompt.ask("Spotify playlist URL")
    with lib.session() as session:
        pm: PlaylistManager = lib.playlist_manager(session)
        playlist = pm.load_playlist(url)
        console.print(
            Panel(
                f"[bold]{playlist.title or '<untitled playlist>'}[/bold]\n\n"
                f"[dim]id[/dim] {playlist.playlist_id}",
                title="Playlist loaded",
                expand=False,
            )
        )


def _load_playlist_by_id(lib: Library) -> None:
    from synciflow.core.playlist_manager import PlaylistManager  # local import for clarity

    playlist_id = Prompt.ask("Spotify playlist ID")
    # Construct a canonical Spotify playlist URL from the ID.
    url = f"https://open.spotify.com/playlist/{playlist_id}"
    with lib.session() as session:
        pm: PlaylistManager = lib.playlist_manager(session)
        playlist = pm.load_playlist(url)
        console.print(
            Panel(
                f"[bold]{playlist.title or '<untitled playlist>'}[/bold]\n\n"
                f"[dim]id[/dim] {playlist.playlist_id}",
                title="Playlist loaded",
                expand=False,
            )
        )


def _list_tracks(lib: Library) -> None:
    with lib.session() as session:
        tracks = session.exec(select(Track)).all()

    if not tracks:
        console.print("[yellow]No tracks found.[/yellow]")
        return

    table = Table(title="Tracks", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Artist", style="magenta")
    table.add_column("Has audio", style="green")

    for t in tracks:
        table.add_row(
            t.track_id,
            t.track_title or "<untitled>",
            t.artist_title or "<unknown>",
            "yes" if t.audio_path else "no",
        )

    console.print(table)

    if not Confirm.ask("Open a track details view?", default=False):
        return

    track_id = Prompt.ask("Track ID")
    _track_details_menu(lib, track_id)


def _track_details_menu(lib: Library, track_id: str) -> None:
    with lib.session() as session:
        track = session.exec(select(Track).where(Track.track_id == track_id)).first()
        if track is None:
            console.print("[red]Track not found.[/red]")
            return

    while True:
        console.print(
            Panel(
                f"[bold]{track.track_title or '<untitled>'}[/bold]\n"
                f"[magenta]{track.artist_title}[/magenta]\n\n"
                f"[dim]id[/dim] {track.track_id}\n"
                f"[dim]path[/dim] {track.audio_path or '<none>'}",
                title="Track details",
                expand=False,
            )
        )
        console.print("  [cyan]1[/cyan] Print file path")
        console.print("  [cyan]2[/cyan] Delete audio file only")
        console.print("  [cyan]3[/cyan] Delete track from DB")
        console.print("  [cyan]4[/cyan] Back")
        choice = Prompt.ask("Choose", choices=["1", "2", "3", "4"], default="4")

        if choice == "1":
            console.print(track.audio_path or "<no audio path>")
        elif choice == "2":
            if not track.audio_path:
                console.print("[yellow]No audio path to delete.[/yellow]")
                continue
            path = Path(track.audio_path)
            if not path.exists():
                console.print("[yellow]File is already missing on disk.[/yellow]")
                continue
            if not Confirm.ask(f"Delete file {path}?", default=False):
                continue
            try:
                path.unlink()
                console.print("[green]Audio file deleted.[/green]")
            except Exception as exc:
                console.print(f"[red]Error deleting file:[/red] {exc}")
        elif choice == "3":
            if not Confirm.ask("Delete DB row for this track?", default=False):
                continue
            with lib.session() as session:
                t = session.exec(select(Track).where(Track.track_id == track_id)).first()
                if t is None:
                    console.print("[yellow]Track already gone.[/yellow]")
                else:
                    session.delete(t)
                    session.commit()
                    console.print("[green]Track deleted from DB.[/green]")
            break
        else:
            break


def _list_playlists(lib: Library) -> None:
    with lib.session() as session:
        playlists = session.exec(select(Playlist)).all()

    if not playlists:
        console.print("[yellow]No playlists found.[/yellow]")
        return

    table = Table(title="Playlists", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")

    for p in playlists:
        table.add_row(p.playlist_id, p.title or "<untitled>")

    console.print(table)

    if not Confirm.ask("Open a playlist details view?", default=False):
        return

    playlist_id = Prompt.ask("Playlist ID")
    _playlist_details_menu(lib, playlist_id)


def _playlist_details_menu(lib: Library, playlist_id: str) -> None:
    with lib.session() as session:
        playlist = session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
        if playlist is None:
            console.print("[red]Playlist not found.[/red]")
            return

        rows = session.exec(
            select(PlaylistTrack, Track)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .where(PlaylistTrack.track_id == Track.track_id)
            .order_by(PlaylistTrack.position)
        ).all()

    table = Table(title=f"Playlist: {playlist.title or playlist_id}", show_lines=False)
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Track ID", style="magenta", no_wrap=True)
    table.add_column("Title", style="bold")

    for rel, track in rows:
        table.add_row(str(rel.position), track.track_id, track.track_title or "<untitled>")

    console.print(table)

    while True:
        console.print("  [cyan]1[/cyan] Local-load/repair playlist from disk")
        console.print("  [cyan]2[/cyan] Delete playlist from DB")
        console.print("  [cyan]3[/cyan] Back")
        choice = Prompt.ask("Choose", choices=["1", "2", "3"], default="3")

        if choice == "1":
            from synciflow.core.playlist_manager import PlaylistManager  # local import

            with lib.session() as session:
                pm: PlaylistManager = lib.playlist_manager(session)
                pm.load_local(playlist_id)
                console.print("[green]Playlist reloaded from local metadata and tracks.[/green]")
        elif choice == "2":
            if not Confirm.ask("Delete playlist DB row (relations only)?", default=False):
                continue
            with lib.session() as session:
                session.exec(delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id))
                p = session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
                if p is not None:
                    session.delete(p)
                session.commit()
            console.print("[green]Playlist deleted from DB.[/green]")
            break
        else:
            break


def run() -> None:
    """
    Entry point for the smart CLI.
    """
    lib = Library.create(AppConfig())
    console.clear()
    _print_header()

    while True:
        choice = _select_main_action()
        if choice == "1":
            _load_track_by_url(lib)
        elif choice == "2":
            _load_track_by_id_local(lib)
        elif choice == "3":
            _load_playlist_by_url(lib)
        elif choice == "4":
            _load_playlist_by_id(lib)
        elif choice == "5":
            _list_tracks(lib)
        elif choice == "6":
            _list_playlists(lib)
        else:
            console.print("[dim]Goodbye.[/dim]")
            break

