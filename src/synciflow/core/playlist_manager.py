from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, delete, select

from synciflow.core.track_manager import TrackManager
from synciflow.core.utils import extract_spotify_id
from synciflow.db.models import Playlist, PlaylistTrack
from synciflow.schemas.playlist import PlaylistDetails
from synciflow.services import spotify_client


@dataclass(frozen=True)
class PlaylistManager:
    session: Session
    tracks: TrackManager

    def load_playlist(self, spotify_playlist_url: str) -> Playlist:
        details: PlaylistDetails = spotify_client.get_playlist_details(spotify_playlist_url)
        playlist_id = details.playlist_id or extract_spotify_id(spotify_playlist_url, "playlist")
        if not playlist_id:
            raise ValueError("Could not determine playlist_id from Spotify URL/details.")

        playlist = self.session.exec(select(Playlist).where(Playlist.playlist_id == playlist_id)).first()
        if playlist is None:
            playlist = Playlist(
                playlist_id=playlist_id,
                playlist_url=details.playlist_url or spotify_playlist_url,
                title=details.title,
                playlist_image_url=details.playlist_image_url,
            )
            self.session.add(playlist)
            self.session.commit()
            self.session.refresh(playlist)
        else:
            playlist.playlist_url = details.playlist_url or playlist.playlist_url
            playlist.title = details.title or playlist.title
            playlist.playlist_image_url = details.playlist_image_url or playlist.playlist_image_url
            self.session.add(playlist)
            self.session.commit()
            self.session.refresh(playlist)

        # Rebuild playlist track relations in order.
        self.session.exec(delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id))
        self.session.commit()

        for pos, track_url in enumerate(details.track_urls or []):
            track = self.tracks.load_track(track_url)
            rel = PlaylistTrack(playlist_id=playlist_id, track_id=track.track_id, position=pos)
            self.session.add(rel)

        self.session.commit()
        return playlist

