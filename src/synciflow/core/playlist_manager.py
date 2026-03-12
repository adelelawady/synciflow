from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from sqlmodel import Session, delete, select

from synciflow.core.track_manager import TrackManager
from synciflow.core.utils import LIKES_PLAYLIST_ID, extract_spotify_id
from synciflow.db.models import Playlist, PlaylistTrack
from synciflow.schemas.playlist import PlaylistDetails
from synciflow.services import spotify_client
from synciflow.storage.file_manager import FileManager
from synciflow.storage.playlist_metadata import (
    PlaylistMetadata,
    read_playlist_metadata,
    write_playlist_metadata,
)


@dataclass(frozen=True)
class PlaylistManager:
    session: Session
    tracks: TrackManager
    files: FileManager

    def _load_from_details(
        self,
        details: PlaylistDetails,
        playlist_id: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
        fallback_url: str = "",
    ) -> Playlist:
        """
        Core implementation for ingesting a playlist from PlaylistDetails.
        """
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
            self.session.refresh(playlist)

        # Rebuild playlist track relations in order.
        self.session.exec(delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id))
        self.session.commit()

        track_ids: List[str] = []
        track_urls = details.track_urls or []
        total = len(track_urls)
        for pos, track_url in enumerate(track_urls):
            # Do not forward the playlist progress callback into TrackManager:
            # TrackManager uses a different callback shape ("started"/"completed").
            track = self.tracks.load_track(track_url)
            rel = PlaylistTrack(playlist_id=playlist_id, track_id=track.track_id, position=pos)
            self.session.add(rel)
            track_ids.append(track.track_id)
            if progress_callback is not None:
                progress_callback(pos + 1, total, track.track_title or track.track_id)

        self.session.commit()

        metadata = PlaylistMetadata(playlist_id=playlist_id, title=playlist.title, track_ids=track_ids)
        write_playlist_metadata(self.files.storage, metadata)

        return playlist

    def load_playlist(
        self,
        spotify_playlist_url: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> Playlist:
        details: PlaylistDetails = spotify_client.get_playlist_details(spotify_playlist_url)
        playlist_id = details.playlist_id or extract_spotify_id(spotify_playlist_url, "playlist")
        if not playlist_id:
            raise ValueError("Could not determine playlist_id from Spotify URL/details.")

        return self._load_from_details(
            details=details,
            playlist_id=playlist_id,
            progress_callback=progress_callback,
            fallback_url=spotify_playlist_url,
        )

    def load_likes(
        self,
        progress_callback: Callable[[int, int, str], None] | None = None,
        login_timeout: int = 120,
        page_load_timeout: int = 30,
        scroll_pause: float = 2.0,
    ) -> Playlist:
        """
        Load Spotify Liked Songs into the library as a pseudo-playlist with a stable ID.
        """
        details = spotify_client.get_likes_details(
            login_timeout=login_timeout,
            page_load_timeout=page_load_timeout,
            scroll_pause=scroll_pause,
        )
        # Enforce the stable likes playlist identifier regardless of adapter behavior.
        return self._load_from_details(
            details=details,
            playlist_id=LIKES_PLAYLIST_ID,
            progress_callback=progress_callback,
            fallback_url=details.playlist_url,
        )

    def load_local(self, playlist_id: str) -> Playlist:
        """
        Local-first playlist load using previously stored playlist metadata and local tracks.
        """
        playlist = self.session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
        if playlist is None:
            playlist = Playlist(playlist_id=playlist_id, playlist_url="", title="", playlist_image_url="")
            self.session.add(playlist)
            self.session.commit()
            self.session.refresh(playlist)

        metadata = read_playlist_metadata(self.files.storage, playlist_id)
        if metadata is None:
            # No metadata available; just return the bare playlist record.
            return playlist

        # Rebuild relations based on stored track_ids order.
        self.session.exec(delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id))
        self.session.commit()

        for pos, track_id in enumerate(metadata.track_ids):
            track = self.tracks.load_local(track_id)
            rel = PlaylistTrack(playlist_id=playlist_id, track_id=track.track_id, position=pos)
            self.session.add(rel)

        self.session.commit()
        return playlist

