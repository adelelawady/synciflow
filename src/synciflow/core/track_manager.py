from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlmodel import Session, select

from synciflow.db.models import Track
from synciflow.schemas.track import TrackDetails
from synciflow.services import downloader as downloader_service
from synciflow.services import spotify_client
from synciflow.services.tagging import ensure_cover_art
from synciflow.storage.file_manager import FileManager

from .utils import extract_spotify_id


@dataclass(frozen=True)
class TrackManager:
    session: Session
    files: FileManager

    def load_track(
        self,
        spotify_url: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> Track:
        track_id_from_url = extract_spotify_id(spotify_url, "track")
        existing = None
        if track_id_from_url:
            existing = self.session.exec(
                select(Track).where(Track.track_id == track_id_from_url)
            ).first()

        details: TrackDetails | None = None
        if existing is None:
            # Track not in DB: need details to create it.
            details = spotify_client.get_track_details(spotify_url)
            track_id = details.track_id or track_id_from_url
            if not track_id:
                raise ValueError("Could not determine track_id from Spotify URL/details.")
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
        else:
            track_id = existing.track_id

        # If audio exists already, ensure DB path is set and return.
        if self.files.exists(track_id):
            audio_path_path = self.files.audio_path(track_id)
            audio_path_str = str(audio_path_path)
            if existing.audio_path != audio_path_str:
                existing.audio_path = audio_path_str
                if existing.downloaded_at is None:
                    existing.downloaded_at = datetime.now(timezone.utc)
                self.session.add(existing)
                self.session.commit()
                self.session.refresh(existing)

            # Ensure cover art is present if we have an image URL.
            ensure_cover_art(audio_path_path, existing.track_image_url)
            return existing

        # Download: need details if we skipped the API call (track was already in DB).
        if details is None:
            details = spotify_client.get_track_details(spotify_url)
        if progress_callback is not None:
            progress_callback("started")
        result = downloader_service.download_track_to_tmp(details, self.files)
        final_path = self.files.atomic_move_to_library(track_id, result.tmp_mp3_path)

        existing.audio_path = str(final_path)
        existing.downloaded_at = datetime.now(timezone.utc)
        self.session.add(existing)
        self.session.commit()
        self.session.refresh(existing)

        # Ensure cover art is embedded for newly downloaded audio.
        ensure_cover_art(final_path, existing.track_image_url)
        if progress_callback is not None:
            progress_callback("completed")
        return existing

    def load_local(self, track_id: str) -> Track:
        """
        Local-first load using an existing audio file on disk.

        - If an mp3 exists for the given track_id, ensure a DB row exists (or repair it)
          and return it.
        - If no mp3 exists, raise a ValueError so callers can surface a clear error.
        """
        audio_path = self.files.audio_path(track_id)
        if not audio_path.exists():
            raise ValueError(f"Local audio file not found for track_id={track_id}")

        track = self.session.exec(select(Track).where(Track.track_id == track_id)).first()
        if track is None:
            track = Track(
                track_id=track_id,
                spotify_url="",
                track_title="",
                artist_title="",
                track_image_url="",
                audio_path=str(audio_path),
                downloaded_at=datetime.now(timezone.utc),
            )
            self.session.add(track)
        else:
            updated = False
            if track.audio_path != str(audio_path):
                track.audio_path = str(audio_path)
                updated = True
            if track.downloaded_at is None:
                track.downloaded_at = datetime.now(timezone.utc)
                updated = True
            if updated:
                self.session.add(track)

        self.session.commit()
        self.session.refresh(track)

        # Ensure cover art is present for local-only loads when an image URL is known.
        ensure_cover_art(audio_path, track.track_image_url)
        return track

