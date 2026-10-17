#!/usr/bin/env python3
"""Prepare reproducible local test media while retaining source-clock provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SOURCE_URL = "https://upload.wikimedia.org/wikipedia/commons/7/79/The_van_in_front_suddenly_changed_lanes_and_caused_the_vehicle_to_rear-end_collision.webm"
SOURCE_PAGE = "https://commons.wikimedia.org/wiki/File:The_van_in_front_suddenly_changed_lanes_and_caused_the_vehicle_to_rear-end_collision.webm"
SOURCE_TITLE = "The van in front suddenly changed lanes and caused the vehicle to rear-end collision.webm"
SOURCE_SHA256 = "73dda42943020ca582f2b2d7c9c054135e3158a1c3bab4ad2092d6acba31293a"
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args: str) -> None:
    subprocess.run(args, check=True, timeout=120)


def probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(result.stdout)
    return {
        "duration_seconds": float(data["format"]["duration"]),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "streams": [
            {"type": stream["codec_type"], "codec": stream["codec_name"]}
            for stream in data["streams"]
        ],
    }


def download(path: Path) -> None:
    temporary = path.with_suffix(".download")
    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": "RewindLocalTest/1.0 (Wikimedia Commons test-media preparation)"
        },
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            temporary.open("wb") as output,
        ):
            count = 0
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                count += len(chunk)
                if count > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Source exceeds the bounded 50 MiB download limit")
                output.write(chunk)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/footage",
    )
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    original = directory / "van-rear-end-original.webm"
    if not original.exists():
        download(original)
    if sha256(original) != SOURCE_SHA256:
        raise ValueError(
            "Original file checksum changed; review source provenance before continuing"
        )
    artifacts = []
    # Every derivative is a contiguous chronological slice. No frames are rearranged.
    for name, start, end in (
        ("incident", 0, 25),
        ("before", 0, 3),
        ("impact", 2, 7),
        ("after", 7, 22),
    ):
        path = directory / f"van-{name}.mp4"
        run(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(original),
            "-t",
            str(end - start),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=960:-2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            str(path),
        )
        artifacts.append(
            {
                "filename": path.name,
                "kind": "video",
                "original_source_start": start,
                "original_source_end": end,
                "time_mapping": f"original_seconds = clip_seconds + {start}",
                **probe(path),
            }
        )
    audio = directory / "van-incident-audio.m4a"
    run(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(original),
        "-t",
        "25",
        "-vn",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-map_metadata",
        "-1",
        str(audio),
    )
    artifacts.append(
        {
            "filename": audio.name,
            "kind": "audio",
            "original_source_start": 0,
            "original_source_end": 25,
            "independent_evidence": False,
            **probe(audio),
        }
    )
    for name, timestamp in (("before", 2), ("after", 8)):
        path = directory / f"van-{name}-frame.jpg"
        run(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            str(original),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-update",
            "1",
            str(path),
        )
        artifacts.append(
            {
                "filename": path.name,
                "kind": "photo",
                "original_source_time": timestamp,
                "independent_evidence": False,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "source_title": SOURCE_TITLE,
        "source_page": SOURCE_PAGE,
        "original_download": SOURCE_URL,
        "upstream_source": "https://www.douyin.com/video/7463173675475291450",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "license_declaration": "Wikimedia Commons declares PD-automated; this is a repository declaration, not an owner-issued CC license. The source page notes jurisdiction-dependent copyright treatment.",
        "attribution": "Wikimedia Commons contributor Fumikas Sagisavas; upstream Douyin video 7463173675475291450; camera overlay FIASNG 2025-01-23. See source page for uploader history.",
        "purpose": "Local development tests only; not part of the synthetic demo and not redistributed in Git.",
        "original": {"filename": original.name, **probe(original)},
        "contact_window_original_seconds": {
            "min": 3,
            "max": 4,
            "basis": "Approximate manual frame review; not an independently verified impact timestamp.",
        },
        "derivation_notice": "All clips, extracted audio and still frames share one original recording. They are not independent corroboration, witness testimony or damage photographs.",
        "artifacts": artifacts,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Prepared {len(artifacts)} derived files; provenance: {directory / 'manifest.json'}"
    )


if __name__ == "__main__":
    main()
