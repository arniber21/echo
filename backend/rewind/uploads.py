"""Bounded, content-validated media ingestion, independent of client filenames and MIME."""

import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from rewind.config import Settings
from rewind.models import MediaFile, SourceType


def captured_at(path: Path) -> datetime | None:
    """Only retain absolute EXIF times with an explicit timezone offset."""
    try:
        with Image.open(path) as image:
            exif = image.getexif().get_ifd(0x8769)
            original, offset = exif.get(0x9003), exif.get(0x9011)
            if original and offset:
                return datetime.strptime(
                    str(original) + str(offset), "%Y:%m:%d %H:%M:%S%z"
                )
    except (ValueError, OSError, KeyError, TypeError):
        pass
    return None


async def inspect_media(path: Path) -> tuple[SourceType, str, float | None]:
    signature = path.read_bytes()[:32] if path.stat().st_size < 32 else b""
    if not signature:
        with path.open("rb") as file:
            signature = file.read(32)
    image_type = None
    if signature.startswith(b"\xff\xd8\xff"):
        image_type = "image/jpeg"
    elif signature.startswith(b"\x89PNG\r\n\x1a\n"):
        image_type = "image/png"
    elif signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
        image_type = "image/webp"
    if image_type:
        try:
            with Image.open(path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise HTTPException(
                415, "The image is corrupt or too large to decode."
            ) from error
        return SourceType.PHOTO, image_type, None
    known_container = (
        signature[4:8] == b"ftyp"
        or signature.startswith((b"\x1aE\xdf\xa3", b"ID3", b"OggS", b"fLaC"))
        or signature.startswith(b"RIFF")
        and signature[8:12] in (b"WAVE", b"AVI ")
        or len(signature) > 1
        and signature[0] == 255
        and signature[1] & 224 == 224
    )
    if not known_container:
        raise HTTPException(
            415,
            "Unsupported media content. Use MP4, WebM, WAV, MP3, M4A, OGG, FLAC, JPEG, PNG, or WebP.",
        )
    try:
        process = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-protocol_whitelist",
            "file",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            503, "Media validation needs ffprobe. Run just setup first."
        ) from error
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=20)
    except TimeoutError as error:
        process.kill()
        await process.communicate()
        raise HTTPException(
            415, "Media could not be validated within the time limit."
        ) from error
    if process.returncode:
        raise HTTPException(415, "Media could not be decoded. The file may be corrupt.")
    probe = json.loads(stdout)
    streams = probe.get("streams", [])
    video = any(
        stream.get("codec_type") == "video"
        and not stream.get("disposition", {}).get("attached_pic")
        for stream in streams
    )
    audio = any(stream.get("codec_type") == "audio" for stream in streams)
    if not video and not audio:
        raise HTTPException(415, "Media has no playable audio or video stream.")
    duration = float(probe.get("format", {}).get("duration", 0))
    if duration <= 0 or duration > 3600:
        raise HTTPException(
            415, "Upload media with a known duration of at most one hour."
        )
    if signature[4:8] == b"ftyp":
        mime = "video/mp4" if video else "audio/mp4"
    elif signature.startswith(b"\x1aE\xdf\xa3"):
        mime = "video/webm" if video else "audio/webm"
    elif signature.startswith(b"RIFF"):
        mime = "video/x-msvideo" if video else "audio/wav"
    elif signature.startswith(b"OggS"):
        mime = "audio/ogg"
    elif signature.startswith(b"fLaC"):
        mime = "audio/flac"
    else:
        mime = "audio/mpeg"
    return SourceType.VIDEO if video else SourceType.AUDIO, mime, duration


async def ingest(
    file: UploadFile, directory: Path, settings: Settings
) -> tuple[MediaFile, Path]:
    source_id = uuid4().hex
    path = directory / source_id
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_file_bytes:
                    raise HTTPException(413, "A file exceeds the upload limit.")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise HTTPException(415, "Empty files cannot be analyzed.")
        kind, mime, duration = await inspect_media(path)
        # Display name only. Disk paths never contain client-supplied text.
        filename = (file.filename or "evidence").replace("\\", "/").split("/")[-1][:180]
        return MediaFile(
            source_id=source_id,
            filename=filename,
            source_type=kind,
            mime_type=mime,
            url=f"/api/media/{source_id}",
            sha256=digest.hexdigest(),
            size_bytes=size,
            duration_seconds=duration,
            captured_at=captured_at(path) if kind == SourceType.PHOTO else None,
        ), path
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
