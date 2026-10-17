#!/usr/bin/env python3
"""Prepare a reviewed set of distinct incidents from the user's local compilation."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple

from prepare_local_incident import DEFAULT_FILENAME, inspect


class Selection(NamedTuple):
    clip_id: str
    start: float
    end: float
    contact_min: float
    contact_max: float
    notes: str


# Original source seconds, reviewed against full-film two-second contact sheets.
# Labels describe visible scenes, not legal fault or injury determinations.
SELECTIONS: list[Selection] = [
    Selection(
        "01-suv-crossing",
        9,
        27,
        17,
        20,
        "Dark vehicles enter the junction; an SUV is displaced across the crossing.",
    ),
    Selection(
        "02-overcast-junction",
        77,
        100.8,
        82,
        86,
        "Overcast junction with a white minibus/van and crossing vehicles; impact and aftermath remain visible.",
    ),
    Selection(
        "03-cross-traffic-contact",
        123,
        139,
        131,
        133,
        "Stationary dashcam observes crossing cars, apparent contact and debris/dust.",
    ),
    Selection(
        "04-police-car-contact",
        184.7,
        203.1,
        187,
        191,
        "A police-marked vehicle crosses close to the camera vehicle; contact and the stopped aftermath are retained.",
    ),
    Selection(
        "05-tree-lined-crossing",
        275.2,
        290.9,
        281,
        286,
        "Vehicles cross a tree-lined intersection beside a pedestrian crossing and metal railing.",
    ),
    Selection(
        "06-white-car-turning",
        291.4,
        304.5,
        296,
        301,
        "Vehicles enter a broad junction beneath a water tower; a white car and dark SUV make visible contact and the white car rotates.",
    ),
    Selection(
        "07-intersection-rollover",
        337.6,
        357.2,
        342,
        346,
        "Crossing vehicles make apparent contact; a dark vehicle overturns to the far side of the junction.",
    ),
    Selection(
        "08-dusk-truck-crossing",
        518.6,
        531.2,
        525,
        529,
        "A large truck crosses at dusk, followed by visible contact between smaller vehicles and a brief flash/sparks.",
    ),
    Selection(
        "09-urban-car-contact",
        562.9,
        576.4,
        567,
        571,
        "Approaching urban intersection; vehicles collide and rotate, with dust/debris visible as a bus passes.",
    ),
    Selection(
        "10-night-overhead",
        613,
        624.6,
        617,
        621,
        "Elevated nighttime camera observes vehicles converging and apparent contact in the junction.",
    ),
    Selection(
        "11-open-road-mini",
        654.4,
        670.9,
        659,
        664,
        "Open-road intersection collision involving a red compact car; subsequent rotation and close aftermath are visible.",
    ),
    Selection(
        "12-city-close-impact",
        727.9,
        738.3,
        731,
        735,
        "City street collision close to the camera, followed by stationary damaged vehicles.",
    ),
    Selection(
        "13-wet-road-impact",
        747.8,
        766.7,
        754,
        758,
        "Wet-road approach to a junction, close contact and an obscured windshield aftermath.",
    ),
    Selection(
        "14-ramp-junction",
        783.9,
        806.7,
        789,
        795,
        "Vehicles enter a signal-controlled intersection near a ramp; crossing contact and stopped aftermath follow.",
    ),
    Selection(
        "15-final-overhead",
        807.2,
        815,
        809,
        813,
        "Final elevated-camera junction incident before the compilation outro; only this short original scene is retained.",
    ),
]


def encode(source: Path, directory: Path, selection: Selection) -> dict:
    clip_id, start, end, impact_min, impact_max, notes = selection
    output = directory / f"{clip_id}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-threads",
            "2",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            str(end - start),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=1280:-2",
            "-filter_threads",
            "1",
            "-c:v",
            "libx264",
            "-threads",
            "2",
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
            str(output),
        ],
        check=True,
        timeout=180,
    )
    result = {
        "clip_id": clip_id,
        "filename": output.name,
        "original_source_start": start,
        "original_source_end": end,
        "requested_duration_seconds": round(end - start, 6),
        "time_mapping": f"original_seconds = clip_seconds + {start}",
        "approximate_contact_original_seconds": {"min": impact_min, "max": impact_max},
        "approximate_contact_clip_seconds": {
            "min": round(impact_min - start, 6),
            "max": round(impact_max - start, 6),
        },
        "review_notes": notes,
        "review_basis": "Human-style visual review of full-film two-second contact sheets, then representative frames from each selected contiguous slice. Contact windows are approximate and unverified.",
        "source_metadata": {
            "label": clip_id.replace("-", " "),
            "recorded_by": "Original camera operator unknown",
            "location": "Not independently established",
            "recorded_at": "Not independently established",
            "notes": f"Local compilation slice, source seconds {start}–{end}. {notes} Uploaded context is user-reported and unverified.",
        },
        "short_scene_note": "The original continuous incident scene is shorter than 15 seconds; no unrelated compilation frames were added."
        if end - start < 15
        else None,
        **inspect(output),
    }
    print(f"Prepared {output.name}: {result['duration_seconds']:.3f}s")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path.home() / "Downloads" / DEFAULT_FILENAME,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/test-clips",
    )
    args = parser.parse_args()
    source = args.input.expanduser().resolve(strict=True)
    directory = args.output_dir.expanduser().resolve()
    if source.parent == directory:
        parser.error("Keep the read-only original outside the output directory")
    original = inspect(source)
    if (
        original["sha256"]
        != "f82bfedc289fac33b38c9fc88f36c69bc8a12901663b8d53572e03285c8c256f"
    ):
        parser.error(
            "This reviewed selection belongs to a different original recording; review new source intervals first"
        )
    for _, start, end, low, high, _ in SELECTIONS:
        if (
            not all(math.isfinite(number) for number in (start, end, low, high))
            or not 0 <= start < end <= original["duration_seconds"]
            or not start <= low <= high <= end
        ):
            parser.error("A reviewed interval is outside the original recording")
    for previous, current in pairwise(SELECTIONS):
        if previous.end > current.start:
            parser.error("Reviewed incident intervals must not overlap")
    directory.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        clips = list(
            pool.map(lambda selection: encode(source, directory, selection), SELECTIONS)
        )
    manifest = {
        "source_path": str(source),
        "source_filename": source.name,
        "source_original": original,
        "prepared_at": datetime.now(UTC).isoformat(),
        "original_preserved": True,
        "license": "Unknown; user-authorized local development use, no redistribution rights asserted.",
        "scan_coverage": {
            "start_seconds": 0,
            "end_seconds": original["duration_seconds"],
            "method": "Full-film contact sheets at 8-second then 2-second spacing, all sheets visually reviewed, plus FFmpeg scene-change candidates at score >0.35. Final outro inspected and excluded.",
            "dense_sample_spacing_seconds": 2,
            "dense_sheet_count": 11,
            "outro_original_start_approximate": 815.2144,
        },
        "clip_count": len(clips),
        "all_clips_are_distinct_original_intervals": True,
        "notice": "These clips show different incidents. Upload each as a separate reconstruction, not as multiple witnesses to one collision. All clocks reset at each clip's start; consult original offsets. No unrelated audio or photos have been added.",
        "clips": clips,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = [
        "# Local intersection test clips",
        "",
        f"{len(clips)} distinct incident clips from the full {original['duration_seconds']:.3f}-second (13m43s) user-provided compilation.",
        "",
        "Upload one MP4 per new reconstruction. These are different incidents, not independent views of a single incident. `manifest.json` contains original offsets, hashes, approximate contact windows and ready-to-use unverified source metadata.",
        "",
        "| Clip | Duration | Original interval |",
        "|---|---:|---:|",
    ]
    for clip in clips:
        rows.append(
            f"| [{clip['filename']}]({clip['filename']}) | {clip['duration_seconds']:.3f}s | {clip['original_source_start']}–{clip['original_source_end']}s |"
        )
    rows.extend(
        [
            "",
            "Shorter clips preserve short original scenes; adjacent unrelated incidents were not used as padding. Source graphics and audio are retained. Contact windows and scene notes are approximate, not verified fault or injury findings. Original remains untouched in Downloads. All files stay outside Git.",
            "",
        ]
    )
    (directory / "README.md").write_text("\n".join(rows))
    print(f"Manifest and upload guide written to {directory}")


if __name__ == "__main__":
    main()
