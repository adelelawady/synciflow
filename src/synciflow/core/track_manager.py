from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from synciflow.db.models import Track
from synciflow.schemas.track import TrackDetails
from synciflow.services import downloader as downloader_service
from synciflow.services import spotify_client
from synciflow.storage.file_manager import FileManager

from .utils import extract_spotify_id


@dataclass(frozen=True)
class TrackManager:
    session: Session
    files: FileManager

    def load_track(self, spotify_url: str) -> Track:
        details: TrackDetails = spotify_client.get_track_details(spotify_url)
        track_id = details.track_id or extract_spotify_id(spotify_url, "track")
        if not track_id:
            raise ValueError("Could not determine track_id from Spotify URL/details.")

        existing = self.session.exec(select(Track).where(Track.track_id == track_id)).first()
        if existing is None:
            existing = Track(
                track_id=track_id,
                spotify_url=details.spotify_url or spotify_url,
                track_title=details.track_title,
                artist_title=details.artist_title,
                track_image_url=details.track_image_url,
            )
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)

        # If audio exists already, ensure DB path is set and return.
        if self.files.exists(track_id):
            audio_path = str(self.files.audio_path(track_id))
            if existing.audio_path != audio_path:
                existing.audio_path = audio_path
                if existing.downloaded_at is None:
                    existing.downloaded_at = datetime.now(timezone.utc)
                self.session.add(existing)
                self.session.commit()
                self.session.refresh(existing)
            return existing

        # Download into tmp then atomically move into library.
        result = downloader_service.download_track_to_tmp(details, self.files)
        final_path = self.files.atomic_move_to_library(track_id, result.tmp_mp3_path)

        existing.audio_path = str(final_path)
        existing.downloaded_at = datetime.now(timezone.utc)
        self.session.add(existing)
        self.session.commit()
        self.session.refresh(existing)
        return existing

