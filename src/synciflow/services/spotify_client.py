from __future__ import annotations

from synciflow.core.utils import LIKES_PLAYLIST_ID
from synciflow.schemas.playlist import PlaylistDetails
from synciflow.schemas.track import TrackDetails


def get_track_details(spotify_track_url: str) -> TrackDetails:
    """
    Thin adapter around `syncify.get_track`.

    Kept as a function so tests can easily monkeypatch it without needing
    to import heavy dependencies in core modules.
    """
    from syncify import get_track  # imported lazily

    t = get_track(spotify_track_url)
    return TrackDetails(
        spotify_url=getattr(t, "spotify_url", spotify_track_url) or spotify_track_url,
        track_id=getattr(t, "track_id", "") or "",
        track_title=getattr(t, "track_title", "") or "",
        artist_title=getattr(t, "artist_title", "") or "",
        track_image_url=getattr(t, "track_image_url", "") or "",
    )


def get_playlist_details(spotify_playlist_url: str) -> PlaylistDetails:
    """
    Thin adapter around `syncify.get_playlist`.
    """
    from syncify import get_playlist  # imported lazily

    p = get_playlist(spotify_playlist_url)
    return PlaylistDetails(
        playlist_url=getattr(p, "playlist_url", spotify_playlist_url) or spotify_playlist_url,
        playlist_id=getattr(p, "playlist_id", "") or "",
        title=getattr(p, "title", "") or "",
        playlist_image_url=getattr(p, "playlist_image_url", "") or "",
        track_urls=list(getattr(p, "track_urls", []) or []),
    )


def get_likes_details(
    login_timeout: int = 120,
    page_load_timeout: int = 30,
    scroll_pause: float = 2.0,
) -> PlaylistDetails:
    """
    Adapter around `syncify.get_likes` that exposes Spotify Liked Songs as a pseudo-playlist.

    Returns a PlaylistDetails object with a stable playlist_id of LIKES_PLAYLIST_ID and
    track_urls populated from the likes scraper.
    """
    try:
        from syncify import get_likes  # imported lazily
    except Exception as exc:  # pragma: no cover - defensive import guard
        raise RuntimeError(f"Failed to import syncify.get_likes: {exc}") from exc

    try:
        likes = get_likes(
            login_timeout=login_timeout,
            page_load_timeout=page_load_timeout,
            scroll_pause=scroll_pause,
        )
    except Exception as exc:
        # Surface a concise, user-facing error; underlying exception can be inspected in logs.
        raise RuntimeError(f"Failed to load Spotify liked songs: {exc}") from exc

    track_urls = list(getattr(likes, "track_urls", []) or [])

    return PlaylistDetails(
        playlist_url="likes://user-liked-songs",
        playlist_id=LIKES_PLAYLIST_ID,
        title="Liked Songs",
        playlist_image_url="",
        track_urls=track_urls,
    )
