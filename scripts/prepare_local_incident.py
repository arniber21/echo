#!/usr/bin/env python3
"""Derive one chronological incident slice from an authorized local recording."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_FILENAME = (
    "Accidents at intersections compilation Cars Accidents - Cars Accidents (1080p).mp4"
)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def run(*arguments: str) -> None:
    subprocess.run(arguments, check=True, timeout=180)


def inspect(path: Path) -> dict:
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
        text=True,
        capture_output=True,
        timeout=30,
    )
    probe = json.loads(result.stdout)
    return {
        "duration_seconds": float(probe["format"]["duration"]),
        "size_bytes": path.stat().st_size,
        "sha256": digest(path),
        "streams": [
            {
                "type": item["codec_type"],
                "codec": item["codec_name"],
                **(
                    {"width": item["width"], "height": item["height"]}
                    if item["codec_type"] == "video"
                    else {}
                ),
            }
            for item in probe["streams"]
        ],
    }


def transcode(source: Path, output: Path, start: float, duration: float) -> None:
    run(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start),
        "-i",
        str(source),
        "-t",
        str(duration),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        "scale=1280:-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        str(output),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path.home() / "Downloads" / DEFAULT_FILENAME,
    )
    parser.add_argument(
        "--start", type=float, required=True, help="Original source offset in seconds"
    )
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="Requested contiguous duration in seconds",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/footage/local-intersection",
    )
    parser.add_argument(
        "--with-derivatives",
        action="store_true",
        help="Also make approach/contact/aftermath fragments, source audio and still frames",
    )
    args = parser.parse_args()
    if (
        not math.isfinite(args.start)
        or not math.isfinite(args.duration)
        or args.start < 0
        or not 0 < args.duration <= 3600
    ):
        parser.error(
            "start must be finite and nonnegative; duration must be within 0–3600 seconds"
        )
    source = args.input.expanduser().resolve(strict=True)
    directory = args.output_dir.expanduser().resolve()
    output_names = {
        "incident.mp4",
        "before.mp4",
        "impact.mp4",
        "after.mp4",
        "incident-audio.m4a",
        "before-frame.jpg",
        "after-frame.jpg",
        "manifest.json",
    }
    if source in {directory / name for name in output_names}:
        parser.error(
            "The original recording cannot be one of the generated output paths"
        )
    original = inspect(source)
    if args.start + args.duration > original["duration_seconds"]:
        parser.error("Requested interval exceeds the original recording")
    directory.mkdir(parents=True, exist_ok=True)
    main_clip = directory / "incident.mp4"
    transcode(source, main_clip, args.start, args.duration)
    artifacts = [
        {
            "filename": main_clip.name,
            "kind": "video",
            "original_source_start": args.start,
            "original_source_end": args.start + args.duration,
            "time_mapping": f"original_seconds = clip_seconds + {args.start}",
            **inspect(main_clip),
        }
    ]
    has_audio = any(item["type"] == "audio" for item in original["streams"])
    if args.with_derivatives:
        # These are temporal thirds, not automatic incident or fault annotations.
        span = args.duration / 3
        for index, name in enumerate(("before", "impact", "after")):
            offset = args.start + span * index
            path = directory / f"{name}.mp4"
            transcode(source, path, offset, span)
            artifacts.append(
                {
                    "filename": path.name,
                    "kind": "video",
                    "original_source_start": offset,
                    "original_source_end": offset + span,
                    "time_mapping": f"original_seconds = clip_seconds + {offset}",
                    "independent_evidence": False,
                    **inspect(path),
                }
            )
        if has_audio:
            audio = directory / "incident-audio.m4a"
            run(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(args.start),
                "-i",
                str(source),
                "-t",
                str(args.duration),
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-map_metadata",
                "-1",
                str(audio),
            )
            artifacts.append(
                {
                    "filename": audio.name,
                    "kind": "audio",
                    "original_source_start": args.start,
                    "original_source_end": args.start + args.duration,
                    "independent_evidence": False,
                    **inspect(audio),
                }
            )
        for name, relative_time in (
            ("before", args.duration / 5),
            ("after", args.duration * 0.8),
        ):
            path = directory / f"{name}-frame.jpg"
            timestamp = args.start + relative_time
            run(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                str(source),
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
                    "sha256": digest(path),
                }
            )
    manifest = {
        "source_path": str(source),
        "source_filename": source.name,
        "prepared_at": datetime.now(UTC).isoformat(),
        "license": "Unknown: user-authorized local development use. No redistribution rights asserted.",
        "original_preserved": True,
        "original": original,
        "selected_interval": {"start": args.start, "end": args.start + args.duration},
        "derivation_notice": "All artifacts derive from one recording; no independent witness testimony or damage photographs were added. Frames remain chronological; cuts remove other compilation incidents. Encoded duration may include one frame or audio packet of padding.",
        "artifacts": artifacts,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {main_clip}; provenance: {directory / 'manifest.json'}")


if __name__ == "__main__":
    main()
