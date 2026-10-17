"""Bounded still-frame preparation with unchanged source clock coordinates."""

import asyncio
import io
from pathlib import Path

from PIL import Image, ImageOps


def sample_times(duration: float, count: int) -> list[float]:
    # Never seek exactly to EOF: most codecs cannot return a frame there.
    end = max(0.0, duration - min(0.1, duration / 2))
    return [end * index / (count - 1) for index in range(count)] if count > 1 else [0.0]


def normalize_image(data: bytes) -> tuple[bytes, int, int]:
    with Image.open(io.BytesIO(data)) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        image.thumbnail((1120, 1120))
        # Padding preserves aspect ratio even for extreme panoramas; boxes refer
        # to this prepared image, never directly to original pixel coordinates.
        image = ImageOps.pad(image, (max(280, image.width), max(280, image.height)))
        output = io.BytesIO()
        image.save(output, "JPEG", quality=85, progressive=False)
        return output.getvalue(), image.width, image.height


async def video_frame(path: Path, source_time: float) -> bytes:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-threads",
        "1",
        "-ss",
        str(source_time),
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        "scale=1120:1120:force_original_aspect_ratio=decrease",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-threads",
        "1",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=30)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    if process.returncode or not output:
        raise ValueError("Frame preparation failed")
    return output
