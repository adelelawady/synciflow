---
name: download-all-tracks-zip
overview: Add API and CLI support to download all tracks in the library as a ZIP archive, mirroring existing playlist ZIP behavior.
todos:
  - id: inspect-track-model-ordering
    content: Inspect Track model and schema to choose a sensible ordering field for all-tracks ZIP (e.g., added_at, title, or artist).
    status: completed
  - id: design-api-endpoint
    content: Design and add the download-all-tracks ZIP endpoint in server.py, reusing playlist ZIP helpers.
    status: completed
  - id: implement-cli-command
    content: Implement _build_library_zip_with_cover and the download-all-tracks-zip Typer command in cli/main.py.
    status: completed
  - id: optional-smart-cli
    content: Optionally add an interactive Smart CLI flow to save all tracks to a ZIP, mirroring playlist flows.
    status: completed
  - id: manual-tests
    content: Run basic manual tests for the new API and CLI behaviors with a sample library.
    status: completed
isProject: false
---

### Goal

Implement an API endpoint and CLI command to **download all tracks in the entire library as a single ZIP**, reusing the existing playlist ZIP patterns (temp copies, embedded cover art, `build_playlist_zip`).

### Key Design Decisions

- **Scope**: All tracks in the library (no playlist filter), consistent with your answer.
- **ZIP construction**: Reuse `build_playlist_zip` from `storage/zip_builder.py`, and follow the playlist flow of copying/retagging files into a temp dir before zipping.
- **Ordering**: Order tracks in a deterministic, user-friendly way; default to `Track.added_at` or `Track.title` if no explicit field exists.
- **Naming**: Use a stable pseudo-playlist id like `"all-tracks"` when calling `build_playlist_zip`, and a human-friendly filename like `"all-tracks.zip"` for downloads and CLI output (unless the user overrides in CLI).

### API Changes

- **Add new endpoint** in `[src/synciflow/api/server.py](src/synciflow/api/server.py)`:
  - Route: `GET /library/download-all-tracks.zip` (or similar `/tracks/download-all.zip`).
  - Handler e.g. `download_all_tracks_zip` that:
    - Opens a DB session via existing `_session` dependency.
    - Queries all `Track` rows with a suitable ordering (e.g. `order_by(Track.added_at, Track.track_id)` or `order_by(Track.title, Track.artist)` depending on available columns).
    - Iterates tracks and for each one with a valid and existing `audio_path`:
      - Constructs a temp working root: `tmp_root = library.files.storage.tmp_dir / "library-zips" / "all-tracks"`.
      - Copies the audio file into `tmp_root / "tracks" / f"{track.track_id}.mp3"`, guarded with `try/except OSError`.
      - Calls `ensure_cover_art(tmp_audio_path, track.track_image_url)` as the playlist endpoint does.
      - Computes a display name using the same helper used for playlist tracks (e.g. `_track_display_name` or `track_display_name`).
      - Appends `(position, track.track_id, display_name, tagged_path)` to a `track_files` list, where `position` is a running index.
    - If `track_files` is empty, returns `404` with a clear message like "No audio files available in library".
    - Calls `build_playlist_zip(library.files, "all-tracks", track_files)` to create the ZIP.
    - Returns a `FileResponse` with `filename="all-tracks.zip"` and `media_type="application/zip"`.
- **Reuse helpers**:
  - Import and reuse the same cover-art/tagging helpers and display-name helper used for playlist downloads to keep consistent file names and tagging.
  - Ensure any needed imports (`Track`, `select`, `Path`, `shutil`, `build_playlist_zip`, `ensure_cover_art`, etc.) are added at the top of `server.py` without duplicating logic.

### CLI Changes (main Typer CLI)

- **Add helper** in `[src/synciflow/cli/main.py](src/synciflow/cli/main.py)` similar to `_build_playlist_zip_with_cover` but for the full library:
  - New function `_build_library_zip_with_cover(lib: Library) -> Path` that:
    - Opens a session and selects all `Track` rows with the same ordering chosen for the API.
    - Uses `tmp_root = lib.files.storage.tmp_dir / "library-zips" / "all-tracks"` (or with a UUID suffix if we want to avoid clashes) and the same "tracks" subdir.
    - For each track with an existing `audio_path`, creates a temp copy, applies `ensure_cover_art`, builds a display name, and populates `track_files`.
    - If `track_files` is empty, prints an error to stderr and exits with non-zero code.
    - Calls `build_playlist_zip(lib.files, "all-tracks", track_files)` and returns the resulting path.
- **Add CLI command** mirroring `download-playlist-zip`/`save-playlist` style:
  - Decorate with `@app.command("download-all-tracks-zip")`.
  - Signature: `def download_all_tracks_zip(out: Path):`.
  - Behavior (per your preference to match existing playlist CLI):
    - Construct `lib = Library.create(AppConfig())`.
    - Call `_build_library_zip_with_cover(lib)` to get `zip_path`.
    - Interpret the `out` argument:
      - If `out` is a directory, set `dest = out / zip_path.name` or `dest = out / "all-tracks.zip"`.
      - If `out` is a file path, use `dest = out` as-is.
    - Call `ensure_parent_dir(dest)` and then `shutil.copyfile(zip_path, dest)`.
    - Print a success message like `"Saved library ZIP to {dest}"`.

### Optional: Smart CLI Integration

- In `[src/synciflow/cli/smart.py](src/synciflow/cli/smart.py)`:
  - Optionally introduce a new menu item such as "Save all tracks to ZIP":
    - Implement `_save_all_tracks_flow(lib: Library)` that parallels `_save_playlist_flow` but does not prompt for playlist id, instead calling `_build_library_zip_with_cover` (imported from `cli.main` or duplicated if necessary).
    - Prompt the user for an output path (file or directory) and copy the ZIP there, with error handling matching other flows.
  - Wire this flow into the main menu (e.g. as a new numbered option) if you want parity in interactive mode.

### Error Handling & Performance Considerations

- **Large libraries**: Document that this operation may be heavy for very large libraries; it is OK to build via temp files (matching existing playlist pattern). If needed later, we can optimize by chunking or excluding extremely large files.
- **Partial failures**: Skip tracks whose files are missing or unreadable (as playlist code already does) and proceed with the rest.
- **Cleanup**: Reuse existing temp-dir patterns; if there is already a cleanup strategy in the app, we rely on that instead of introducing new behavior here.

### Testing & Verification Strategy

- **API manual test**: Use `curl` or a browser to hit `/library/download-all-tracks.zip` and verify:
  - Response status `200`, content-type `application/zip`.
  - The ZIP contains expected tracks, named consistently (e.g. `001-Title - Artist.mp3`, etc.).
- **CLI manual test**: Run `python -m synciflow.cli.main download-all-tracks-zip out.zip` (or via the installed entry point) and verify:
  - Command exits successfully and prints the success message.
  - `out.zip` exists and contains all expected tracks with proper names and cover art.
- **Edge case test**: Run both API and CLI in a library where some tracks have missing `audio_path` and confirm they are skipped without failing the whole operation, matching playlist behavior.

