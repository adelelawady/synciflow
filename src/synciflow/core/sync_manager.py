from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlmodel import Session, delete, func, select

from synciflow.core.utils import LIKES_PLAYLIST_ID, extract_spotify_id
from synciflow.db.models import Playlist, PlaylistTrack, Track
from synciflow.schemas.playlist import PlaylistDetails
from synciflow.services import spotify_client

from .track_manager import TrackManager


@dataclass(frozen=True)
class SyncResult:
    added: int
    removed: int
    kept: int


@dataclass(frozen=True)
class SyncManager:
    session: Session
    tracks: TrackManager

    def _sync_from_details(
        self,
        details: PlaylistDetails,
        playlist_id: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
        fallback_url: str = "",
    ) -> SyncResult:
        playlist = self.session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
        if playlist is None:
            playlist = Playlist(
                playlist_id=playlist_id,
                playlist_url=details.playlist_url or fallback_url,
                title=details.title,
                playlist_image_url=details.playlist_image_url,
            )
            self.session.add(playlist)
            self.session.commit()
            self.session.refresh(playlist)
        else:
            playlist.playlist_url = details.playlist_url or playlist.playlist_url or fallback_url
            playlist.title = details.title or playlist.title
            playlist.playlist_image_url = details.playlist_image_url or playlist.playlist_image_url
            self.session.add(playlist)
            self.session.commit()

        desired_track_urls = list(details.track_urls or [])
        desired_track_ids = [extract_spotify_id(u, "track") for u in desired_track_urls]

        # current relations
        current_rows = list(
            self.session.exec(select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)).all()
        )
        current_ids = [r.track_id for r in current_rows]

        desired_set = set([tid for tid in desired_track_ids if tid])
        current_set = set(current_ids)

        to_add = desired_set - current_set
        to_remove = current_set - desired_set
        kept = len(desired_set & current_set)

        # Add missing tracks + relations (and update positions for all)
        self.session.exec(delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id))
        self.session.commit()

        total = len(desired_track_urls)
        for pos, track_url in enumerate(desired_track_urls):
            track = self.tracks.load_track(track_url)
            self.session.add(PlaylistTrack(playlist_id=playlist_id, track_id=track.track_id, position=pos))
            if progress_callback is not None:
                progress_callback(pos + 1, total, "Syncing tracks")
        self.session.commit()

        # Remove unreferenced tracks from disk + DB.
        removed_count = 0
        for track_id in to_remove:
            # Count remaining references in other playlists.
            ref_count = self.session.exec(
                select(func.count()).select_from(PlaylistTrack).where(PlaylistTrack.track_id == track_id)
            ).one()
            if int(ref_count) == 0:
                track = self.session.exec(select(Track).where(Track.track_id == track_id)).first()
                if track is not None:
                    self.tracks.files.delete(track_id)
                    self.session.delete(track)
                    self.session.commit()
                removed_count += 1

        playlist.last_synced_at = datetime.now(timezone.utc)
        self.session.add(playlist)
        self.session.commit()

        if progress_callback is not None:
            progress_callback(total, total, f"Done: added={len(to_add)}, removed={removed_count}, kept={kept}")

        return SyncResult(added=len(to_add), removed=removed_count, kept=kept)

    def sync_playlist(
        self,
        spotify_playlist_url: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> SyncResult:
        details = spotify_client.get_playlist_details(spotify_playlist_url)
        playlist_id = details.playlist_id or extract_spotify_id(spotify_playlist_url, "playlist")
        if not playlist_id:
            raise ValueError("Could not determine playlist_id from Spotify URL/details.")

        return self._sync_from_details(
            details=details,
            playlist_id=playlist_id,
            progress_callback=progress_callback,
            fallback_url=spotify_playlist_url,
        )

    def sync_likes(
        self,
        progress_callback: Callable[[int, int, str], None] | None = None,
        login_timeout: int = 120,
        page_load_timeout: int = 30,
        scroll_pause: float = 2.0,
    ) -> SyncResult:
        """
        Sync Spotify Liked Songs into the library as a pseudo-playlist.
        """
        details = spotify_client.get_likes_details(
            login_timeout=login_timeout,
            page_load_timeout=page_load_timeout,
            scroll_pause=scroll_pause,
        )
        # Enforce the stable likes playlist identifier regardless of adapter behavior.
        return self._sync_from_details(
            details=details,
            playlist_id=LIKES_PLAYLIST_ID,
            progress_callback=progress_callback,
            fallback_url=details.playlist_url,
        )
