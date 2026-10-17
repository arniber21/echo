"""Conservative same-recording placement from visual pixels, without model inference.

This recognizes unchanged/re-encoded excerpts and exported stills, not independent
camera viewpoints. Missing results mean unknown alignment, never an offset of zero.
"""

import asyncio
import hashlib
import math
import sys
from array import array
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat
from pydantic import BaseModel, ConfigDict, Field

from rewind.models import MediaFile, SourceType

from .cache import JsonCache, cache_key

VERSION = "pixel-content-alignment-v1"
FPS = 4
WIDTH, HEIGHT = 32, 18
FRAME_BYTES = WIDTH * HEIGHT * 3
MAX_FRAMES = 1200
MAX_SOURCES = 12
MAX_ERROR = 0.045
MIN_MARGIN = 0.003


@dataclass(frozen=True)
class ContentAlignment:
    offset_seconds: float
    uncertainty_seconds: float
    confidence: float
    basis: str


class _Frames(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frames: list[str] = Field(max_length=MAX_FRAMES)


class _AudioEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    energy: list[float] = Field(max_length=3000)


async def _decode_audio(path: Path, duration: float) -> list[float]:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-threads",
        "1",
        "-i",
        str(path),
        "-t",
        str(min(300, duration)),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "8000",
        "-f",
        "s16le",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        raw, _ = await asyncio.wait_for(process.communicate(), timeout=25)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    if process.returncode or not raw or len(raw) % 2:
        raise ValueError("Bounded audio decoding failed")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    return [
        math.sqrt(sum(value * value for value in samples[index : index + 800]) / 800)
        for index in range(0, len(samples) - 799, 800)
    ]


async def _audio_envelope(
    source: MediaFile, path: Path, cache: JsonCache
) -> list[float]:
    digest = await asyncio.to_thread(_digest, path)
    key = cache_key(
        {
            "version": "audio-content-envelope-v1",
            "sha256": digest,
            "duration": source.duration_seconds,
        }
    )
    stored = await asyncio.to_thread(cache.read, key, _AudioEnvelope)
    if (
        stored is not None
        and stored.energy
        and all(value >= 0 for value in stored.energy)
    ):
        return stored.energy
    energy = await _decode_audio(path, source.duration_seconds or 0)
    try:
        await asyncio.to_thread(cache.write, key, _AudioEnvelope(energy=energy))
    except OSError:
        pass
    return energy


def _correlation(a: list[float], b: list[float]) -> float:
    average_a, average_b = sum(a) / len(a), sum(b) / len(b)
    centered_a = [value - average_a for value in a]
    centered_b = [value - average_b for value in b]
    denominator = math.sqrt(
        sum(value * value for value in centered_a)
        * sum(value * value for value in centered_b)
    )
    return (
        sum(left * right for left, right in zip(centered_a, centered_b, strict=True))
        / denominator
        if denominator > 1e-8
        else 0
    )


def _match_audio(parent: list[float], child: list[float]) -> ContentAlignment | None:
    if len(child) < 30 or len(child) > len(parent):
        return None
    mean = sum(child) / len(child)
    deviation = math.sqrt(sum((value - mean) ** 2 for value in child) / len(child))
    if mean < 1 or deviation / max(mean, 1) < 0.05:
        return None
    scores = [
        (_correlation(parent[offset : offset + len(child)], child), offset)
        for offset in range(len(parent) - len(child) + 1)
    ]
    scores.sort(reverse=True)
    best, offset = scores[0]
    if best < 0.985:
        return None
    alternatives = [value for value, position in scores if abs(position - offset) > 3]
    if alternatives and best - max(alternatives) < 0.04:
        return None
    # Independent thirds must agree on the same offset, rather than one loud
    # spike dominating a whole-recording correlation.
    for third in range(3):
        start, end = third * len(child) // 3, (third + 1) * len(child) // 3
        if _correlation(parent[offset + start : offset + end], child[start:end]) < 0.96:
            return None
    return ContentAlignment(
        offset / 10,
        0.2,
        min(0.99, best),
        f"Decoded mono audio-track match: 100ms energy-envelope correlation {best:.6f}, confirmed independently in three separated segments. Sampling uncertainty ±0.2s; silent, flat, repeated and competing offsets are rejected. This matches a recording track, not spoken testimony.",
    )


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _descriptor(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    return image.filter(ImageFilter.GaussianBlur(0.5)).tobytes()


def _distance(a: bytes, b: bytes) -> float:
    return sum(abs(left - right) for left, right in zip(a, b, strict=True)) / (
        FRAME_BYTES * 255
    )


def _informative(frame: bytes) -> bool:
    image = Image.frombytes("RGB", (WIDTH, HEIGHT), frame)
    return max(ImageStat.Stat(image).stddev) >= 12


async def _decode(path: Path, duration: float) -> list[bytes]:
    """One bounded decoder process per video; never full-resolution frame storage."""
    count = min(MAX_FRAMES, max(1, math.ceil(duration * FPS)))
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-threads",
        "1",
        "-i",
        str(path),
        "-an",
        "-vf",
        f"fps={FPS},scale={WIDTH}:{HEIGHT}:flags=lanczos,gblur=sigma=0.5",
        "-frames:v",
        str(count),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-threads",
        "1",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        raw, _ = await asyncio.wait_for(process.communicate(), timeout=25)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    if process.returncode or not raw or len(raw) % FRAME_BYTES:
        raise ValueError("Bounded visual decoding failed")
    return [
        raw[index : index + FRAME_BYTES] for index in range(0, len(raw), FRAME_BYTES)
    ]


def _photo(path: Path) -> list[bytes]:
    with Image.open(path) as image:
        return [_descriptor(image)]


async def _frames(source: MediaFile, path: Path, cache: JsonCache) -> list[bytes]:
    digest = await asyncio.to_thread(_digest, path)
    key = cache_key(
        {
            "version": VERSION,
            "role": "descriptors",
            "sha256": digest,
            "duration": source.duration_seconds,
            "type": source.source_type.value,
        }
    )
    stored = await asyncio.to_thread(cache.read, key, _Frames)
    if stored is not None:
        try:
            frames = [bytes.fromhex(value) for value in stored.frames]
            if frames and all(len(frame) == FRAME_BYTES for frame in frames):
                return frames
        except ValueError:
            pass
    frames = (
        await _decode(path, source.duration_seconds or 0)
        if source.source_type == SourceType.VIDEO
        else await asyncio.to_thread(_photo, path)
    )
    try:
        await asyncio.to_thread(
            cache.write, key, _Frames(frames=[frame.hex() for frame in frames])
        )
    except OSError:
        pass
    return frames


def _match(
    parent: list[bytes], child: list[bytes], *, photo: bool
) -> ContentAlignment | None:
    if photo:
        indices = [0]
    else:
        if len(child) < 8:
            return None
        indices = sorted(
            {
                round((len(child) - 1) * fraction)
                for fraction in (0.15, 0.325, 0.5, 0.675, 0.85)
            }
        )
        # Unchanging excerpts cannot establish an offset from a static/repeated scene.
        if (
            max(_distance(child[indices[0]], child[index]) for index in indices[1:])
            < 0.008
        ):
            return None
    if any(not _informative(child[index]) for index in indices):
        return None
    candidates = []
    # All separated sampled frames must support ONE unit-speed offset.
    # A negative offset would place a partial longer recording before the anchor;
    # this matcher intentionally handles fully contained excerpts only.
    for offset in range(
        max(0, len(parent) - len(child) + 1) if not photo else len(parent)
    ):
        errors = [_distance(parent[offset + index], child[index]) for index in indices]
        candidates.append((sum(errors) / len(errors), offset, max(errors)))
    if not candidates:
        return None
    candidates.sort()
    best, offset, worst = candidates[0]
    if best > MAX_ERROR or worst > MAX_ERROR * 1.5:
        return None
    # Compare an alternative outside the finite sampling error window. Multiple
    # identical or near-identical locations (static/replayed footage) stay unknown.
    alternatives = [
        error for error, position, _ in candidates if abs(position - offset) > 2
    ]
    if not alternatives:
        return None
    alternative = min(alternatives)
    if alternative - best < max(MIN_MARGIN, best * 0.4):
        return None
    # Individually best correspondences also need unit-speed agreement. This
    # rejects sped-up/slowed-down scenes that happen to give a decent average.
    if not photo:
        for index in indices:
            errors = [_distance(frame, child[index]) for frame in parent]
            nearest = min(range(len(errors)), key=errors.__getitem__)
            if abs(nearest - (offset + index)) > 2:
                return None
    quality = max(0, 1 - best / MAX_ERROR)
    separation = min(1, (alternative - best) / 0.04)
    confidence = min(0.99, 0.7 + 0.2 * quality + 0.09 * separation)
    return ContentAlignment(
        offset / FPS,
        0.5,
        confidence,
        "Visual pixel-content match against the primary recording: "
        + (
            "one uniquely matching exported still"
            if photo
            else f"{len(indices)} separated frames with a consistent unit-speed offset"
        )
        + f"; normalized mean error {best:.5f}, competing-location margin {alternative - best:.5f}. Sampling uncertainty ±0.5s; no independent-camera synchronization inferred.",
    )


async def find_content_alignments(
    media: list[MediaFile], paths: Mapping[str, Path], cache: JsonCache
) -> dict[str, ContentAlignment]:
    """Return supported placements only, bounded to twelve sources and 300s/video.

    The longest video anchors the clock. Metadata and filenames are never inputs
    to matching. Independent views and ambiguous/unsupported evidence stay absent.
    Audio is matched only to the parent's actual decoded audio track. Local
    decoder/cache failures are auxiliary and leave those sources absent too.
    """
    videos = sorted(
        (
            source
            for source in media
            if source.source_type == SourceType.VIDEO
            and source.duration_seconds
            and source.duration_seconds > 0
        ),
        key=lambda source: (-source.duration_seconds, source.sha256, source.source_id),
    )
    if not videos:
        return {}
    anchor = videos[0]
    result = {
        anchor.source_id: ContentAlignment(
            0,
            0,
            1,
            "Primary clock: longest video; source and case timestamps are identical.",
        )
    }
    if anchor.duration_seconds > MAX_FRAMES / FPS:
        return result
    try:
        parent = await _frames(anchor, paths[anchor.source_id], cache)
    except (KeyError, OSError, ValueError, TimeoutError):
        return result
    limit = asyncio.Semaphore(2)
    candidates = sorted(
        (
            source
            for source in media
            if source.source_id != anchor.source_id
            and source.source_type
            in {SourceType.VIDEO, SourceType.PHOTO, SourceType.AUDIO}
        ),
        key=lambda source: (source.sha256, source.source_id),
    )[: MAX_SOURCES - 1]
    parent_audio = None
    if any(source.source_type == SourceType.AUDIO for source in candidates):
        try:
            parent_audio = await _audio_envelope(anchor, paths[anchor.source_id], cache)
        except (KeyError, OSError, ValueError, TimeoutError):
            pass

    async def align(source: MediaFile) -> tuple[str, ContentAlignment | None]:
        try:
            if source.source_type in {SourceType.VIDEO, SourceType.AUDIO} and (
                not source.duration_seconds
                or source.duration_seconds > anchor.duration_seconds
            ):
                return source.source_id, None
            async with limit:
                if source.source_type == SourceType.AUDIO:
                    if parent_audio is None:
                        return source.source_id, None
                    child_audio = await _audio_envelope(
                        source, paths[source.source_id], cache
                    )
                    return source.source_id, await asyncio.to_thread(
                        _match_audio, parent_audio, child_audio
                    )
                child = await _frames(source, paths[source.source_id], cache)
                match = await asyncio.to_thread(
                    _match, parent, child, photo=source.source_type == SourceType.PHOTO
                )
            return source.source_id, match
        except (KeyError, OSError, ValueError, TimeoutError):
            return source.source_id, None

    for identity, alignment in await asyncio.gather(
        *(align(source) for source in candidates)
    ):
        if alignment is not None:
            result[identity] = alignment
    return result
