from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

#from synciflow.core.utils import LIKES_PLAYLIST_ID
from synciflow.schemas.playlist import PlaylistDetails
from synciflow.schemas.track import TrackDetails, _ms_to_duration_str

from spotapi.playlist import PublicPlaylist
from spotapi.song import Song

_SPOTIFY_TRACK_RE = re.compile(r"(?:spotify:track:|/track/)([A-Za-z0-9]+)")
_SPOTIFY_PLAYLIST_RE = re.compile(r"(?:spotify:playlist:|/playlist/)([A-Za-z0-9]+)")


def _extract_spotify_id(url: str, kind: str) -> str:
    if not url:
        return ""

    if kind == "track":
        m = _SPOTIFY_TRACK_RE.search(url)
    else:
        m = _SPOTIFY_PLAYLIST_RE.search(url)

    if not m:
        return ""

    return m.group(1) or ""


def _make_spotify_track_url(track_id: str) -> str:
    if not track_id:
        return ""
    return f"https://open.spotify.com/track/{track_id}"


def _extract_track_artist(track: Dict[str, Any]) -> str:
    first_artist = track.get("firstArtist") or {}
    if isinstance(first_artist, dict):
        items = first_artist.get("items") or []
        if items and isinstance(items[0], dict):
            profile = items[0].get("profile") or {}
            name = profile.get("name")
            if name:
                return str(name)

    other_artists = track.get("otherArtists") or {}
    if isinstance(other_artists, dict):
        items = other_artists.get("items") or []
        if items and isinstance(items[0], dict):
            profile = items[0].get("profile") or {}
            name = profile.get("name")
            if name:
                return str(name)

    return ""


def _extract_track_image_url(track: Dict[str, Any]) -> str:
    # Prefer album cover art
    album = track.get("albumOfTrack") or {}
    if isinstance(album, dict):
        cover_art = album.get("coverArt") or {}
        if isinstance(cover_art, dict):
            sources = cover_art.get("sources") or []
            if isinstance(sources, list) and sources:
                first = sources[0]
                if isinstance(first, dict):
                    url = first.get("url")
                    if url:
                        return str(url)

    # Fallback to track visual identity
    visual = track.get("visualIdentity") or {}
    if isinstance(visual, dict):
        square = visual.get("squareCoverImage") or {}
        if isinstance(square, dict):
            sources = square.get("sources") or []
            if isinstance(sources, list) and sources:
                first = sources[0]
                if isinstance(first, dict):
                    url = first.get("url")
                    if url:
                        return str(url)

    return ""


def get_track_details(spotify_track_url: str) -> TrackDetails:
    track_id = _extract_spotify_id(spotify_track_url, "track")
    if not track_id:
        raise ValueError(f"Could not extract track id from '{spotify_track_url}'")

    try:
        song = Song()
        resp = song.get_track_info(track_id)
    except Exception as exc:
        raise RuntimeError(f"Failed to load Spotify track details: {exc}") from exc

    track = (resp.get("data", {}) or {}).get("trackUnion", {}) or {}

    spotify_url = (
        track.get("sharingInfo", {}).get("shareUrl")
        or _make_spotify_track_url(track.get("uri") or track.get("id") or track_id)
        or spotify_track_url
    )

    # Duration lives at trackUnion.duration.totalMilliseconds
    duration_ms = int(
        (track.get("duration") or {}).get("totalMilliseconds") or 0
    )

    return TrackDetails(
        spotify_url=str(spotify_url or ""),
        track_id=str(track.get("id") or track_id or ""),
        track_title=str(track.get("name") or ""),
        artist_title=_extract_track_artist(track),
        track_image_url=_extract_track_image_url(track),
        duration_ms=duration_ms,
        duration_str=_ms_to_duration_str(duration_ms),
    )


def _extract_playlist_image_url(playlist_data: Dict[str, Any]) -> str:
    if not isinstance(playlist_data, dict):
        return ""

    images = playlist_data.get("images") or {}
    if isinstance(images, dict):
        items = images.get("items") or []
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                sources = first.get("sources") or []
                if isinstance(sources, list) and sources:
                    first_src = sources[0]
                    if isinstance(first_src, dict):
                        return str(first_src.get("url") or "")

    return ""


def get_playlist_details(spotify_playlist_url: str) -> PlaylistDetails:
    """Fetch Spotify playlist metadata using spotapi."""

    playlist_id = _extract_spotify_id(spotify_playlist_url, "playlist")

    try:
        playlist = PublicPlaylist(spotify_playlist_url)
        info = playlist.get_playlist_info(limit=100)
    except Exception as exc:
        raise RuntimeError(f"Failed to load Spotify playlist details: {exc}") from exc

    playlist_data = (info.get("data", {}) or {}).get("playlistV2", {}) or {}
    title = str(playlist_data.get("name") or "")
    image_url = _extract_playlist_image_url(playlist_data)

    track_urls: List[str] = []
    try:
        for chunk in playlist.paginate_playlist():
            items = chunk.get("items") or []
            for item in items:
                track = (item.get("itemV2", {}) or {}).get("data", {}) or {}
                uri = track.get("uri") or track.get("id") or ""
                if not uri:
                    continue
                track_id = _extract_spotify_id(uri, "track")
                if not track_id and uri.startswith("spotify:track:"):
                    track_id = uri.split("spotify:track:")[-1]
                if track_id:
                    track_urls.append(_make_spotify_track_url(track_id))
    except Exception:
        # Best-effort; if pagination fails, continue with what we have.
        pass

    return PlaylistDetails(
        playlist_url=str(getattr(playlist, "playlist_link", spotify_playlist_url) or spotify_playlist_url),
        playlist_id=str(playlist_id or ""),
        title=title,
        playlist_image_url=image_url,
        track_urls=track_urls,
    )




def get_likes_details(
    login_timeout: int = 120,
    page_load_timeout: int = 30,
    scroll_pause: float = 2.0,
) -> PlaylistDetails:
    """Fetch Spotify playlist metadata using spotapi."""
    return PlaylistDetails(
        playlist_url="",
        playlist_id="",
        title="",
        playlist_image_url="",
        track_urls=[],
    )
