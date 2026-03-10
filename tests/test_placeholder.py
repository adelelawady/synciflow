from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from synciflow.config import AppConfig
from synciflow.core.library_manager import Library
from synciflow.schemas.playlist import PlaylistDetails
from synciflow.schemas.track import TrackDetails


def test_path_manager_prefix(tmp_path: Path):
    from synciflow.storage.path_manager import StoragePaths, track_audio_path

    storage = StoragePaths(root=tmp_path)
    p = track_audio_path(storage, "abcd1234")
    assert p.as_posix().endswith("/tracks/ab/abcd1234.mp3")


def test_file_manager_atomic_move(tmp_path: Path):
    from synciflow.storage.file_manager import FileManager
    from synciflow.storage.path_manager import StoragePaths

    fm = FileManager(StoragePaths(root=tmp_path))
    fm.init_storage()
    tmp_mp3 = tmp_path / "tmp" / "x.mp3"
    tmp_mp3.write_bytes(b"mp3data")

    final = fm.atomic_move_to_library("zz99", tmp_mp3)
    assert final.exists()
    assert final.read_bytes() == b"mp3data"
    assert not tmp_mp3.exists()


def test_track_manager_load_track_uses_fake_downloader(monkeypatch, tmp_path: Path):
    cfg = AppConfig(storage_root=tmp_path / "storage", data_root=tmp_path / "data")
    lib = Library.create(cfg)

    def fake_get_track_details(url: str) -> TrackDetails:
        return TrackDetails(
            spotify_url=url,
            track_id="t123",
            track_title="Song",
            artist_title="Artist",
            track_image_url="",
        )

    def fake_download_track_to_tmp(details: TrackDetails, file_manager):
        file_manager.init_storage()
        p = file_manager.storage.tmp_dir / "tmp.mp3"
        p.write_bytes(b"abc")
        from synciflow.services.downloader import DownloadResult

        return DownloadResult(youtube_video_id="vid", tmp_mp3_path=p)

    monkeypatch.setattr("synciflow.services.spotify_client.get_track_details", fake_get_track_details)
    monkeypatch.setattr("synciflow.services.downloader.download_track_to_tmp", fake_download_track_to_tmp)

    with lib.session() as session:
        tm = lib.track_manager(session)
        t = tm.load_track("https://open.spotify.com/track/t123")
        assert t.track_id == "t123"
        assert Path(t.audio_path).exists()


def test_sync_manager_removes_unreferenced_track(monkeypatch, tmp_path: Path):
    cfg = AppConfig(storage_root=tmp_path / "storage", data_root=tmp_path / "data")
    lib = Library.create(cfg)

    # Seed two tracks and one playlist relation, with audio files.
    with lib.session() as session:
        tm = lib.track_manager(session)

        def fake_get_track_details(url: str) -> TrackDetails:
            track_id = url.rsplit("/", 1)[-1]
            return TrackDetails(spotify_url=url, track_id=track_id, track_title=track_id, artist_title="a")

        def fake_download_track_to_tmp(details: TrackDetails, file_manager):
            file_manager.init_storage()
            p = file_manager.storage.tmp_dir / f"{details.track_id}.mp3"
            p.write_bytes(b"x")
            from synciflow.services.downloader import DownloadResult

            return DownloadResult(youtube_video_id="vid", tmp_mp3_path=p)

        monkeypatch.setattr("synciflow.services.spotify_client.get_track_details", fake_get_track_details)
        monkeypatch.setattr("synciflow.services.downloader.download_track_to_tmp", fake_download_track_to_tmp)

        # Load playlist initially with two tracks.
        def fake_playlist_details_initial(url: str) -> PlaylistDetails:
            return PlaylistDetails(
                playlist_url=url,
                playlist_id="p1",
                title="P",
                playlist_image_url="",
                track_urls=[
                    "https://open.spotify.com/track/t1",
                    "https://open.spotify.com/track/t2",
                ],
            )

        monkeypatch.setattr("synciflow.services.spotify_client.get_playlist_details", fake_playlist_details_initial)
        pm = lib.playlist_manager(session)
        pm.load_playlist("https://open.spotify.com/playlist/p1")

        # Sync now with only one track remaining.
        def fake_playlist_details_after(url: str) -> PlaylistDetails:
            return PlaylistDetails(
                playlist_url=url,
                playlist_id="p1",
                title="P",
                playlist_image_url="",
                track_urls=["https://open.spotify.com/track/t1"],
            )

        monkeypatch.setattr("synciflow.services.spotify_client.get_playlist_details", fake_playlist_details_after)
        sm = lib.sync_manager(session)
        res = sm.sync_playlist("https://open.spotify.com/playlist/p1")
        assert res.removed >= 1

