from __future__ import annotations

from pathlib import Path
from typing import Optional
import mimetypes
import urllib.request

from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp3 import MP3


def _guess_mime_type_from_url(url: str) -> str:
    mime, _ = mimetypes.guess_type(url)
    return mime or "image/jpeg"


def ensure_cover_art(mp3_path: Path, image_url: Optional[str]) -> Path:
    """
    Ensure that the given MP3 file has embedded cover art.

    - If image_url is falsy, the file is returned unchanged.
    - If the file already has an APIC frame, it is returned unchanged.
    - Otherwise, the image is downloaded and embedded as an APIC frame.
    """
    if not image_url:
        return mp3_path

    if not mp3_path.exists():
        return mp3_path

    try:
        audio = MP3(mp3_path)
    except Exception:
        return mp3_path

    # If there are already APIC frames, leave as-is.
    try:
        id3 = ID3(mp3_path)
        if any(key.startswith("APIC") for key in id3.keys()):
            return mp3_path
    except ID3NoHeaderError:
        id3 = ID3()

    try:
        with urllib.request.urlopen(image_url) as resp:
            image_data = resp.read()
            mime = resp.headers.get_content_type() or _guess_mime_type_from_url(image_url)
    except Exception:
        return mp3_path

    try:
        id3.add(
            APIC(
                encoding=3,
                mime=mime,
                type=3,
                desc="Cover",
                data=image_data,
            )
        )
        id3.save(mp3_path)
    except Exception:
        return mp3_path

    return mp3_path

