#!/usr/bin/env python3
"""Prepare reviewed incident scenes from two additional local compilations."""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple

from prepare_local_incident import inspect

DEFAULT_DIRECTORY = "drive-download-20261017T194907Z-1-001"
SOURCES = {
    "tennessee": (
        "Best of TENNESSEE Drivers 20 Minutes of Dashcam Videos PART 2 - Dashcam Lessons (1080p).mp4",
        "e047c5e6ca3a51d6e963cf8505fe43a2b383be7dc02b52fe24e6814f6c3318c7",
    ),
    "playback": (
        "videoplayback.mp4",
        "a4503767cce48f6f6946697859c328b464eaec6a743432dc7aef30d2a0ed5bae",
    ),
}


class Selection(NamedTuple):
    clip_id: str
    source: str
    start: float
    end: float
    notes: str


SELECTIONS = [
    Selection(
        "01-mountain-road",
        "tennessee",
        14,
        38,
        "Wooded two-lane road approach, followed by edited roadside footage showing damaged vehicles. The inserted roadside conversation is not a continuous dashcam clock.",
    ),
    Selection(
        "02-tree-lined-road",
        "tennessee",
        498,
        520,
        "Wooded two-lane road approach, camera displacement toward vegetation, followed by an edited replay with text overlays. Replay is not a second incident.",
    ),
    Selection(
        "03-truck-side-views",
        "tennessee",
        578,
        630,
        "A white tractor-trailer passes close to the camera vehicle beside a concrete barrier. The compilation includes several camera views/replays and a damage still; their chronology is edited.",
    ),
    Selection(
        "04-junction-airbag",
        "tennessee",
        740,
        770,
        "Junction approach with crossing traffic, abrupt camera obscuration, then compilation-inserted damage photographs. Subtitle injury and insurance claims are not verified.",
    ),
    Selection(
        "05-motorcycle-interaction",
        "tennessee",
        846,
        922,
        "A motorcycle and white hatchback travel and stop near one another at successive traffic lights. No collision is visible in these reviewed frames; useful for testing restraint on ambiguous interactions.",
    ),
    Selection(
        "06-cloudy-box-truck",
        "tennessee",
        1174,
        1188,
        "A white box truck enters the road close to the approaching dashcam under dark clouds. No contact is visible in reviewed frames; a near-miss candidate, not a confirmed crash.",
    ),
    Selection(
        "07-bridge-close-pass",
        "playback",
        0,
        26,
        "Silver car passes close beside the dashcam on a bridge; the compilation repeats the close approach with explanatory subtitles. Treat replay frames as repeated evidence.",
    ),
    Selection(
        "08-dusk-junction",
        "playback",
        612,
        632,
        "Dusk junction with a red vehicle in front of the camera and crossing vehicles; collision, dust or smoke, then close aftermath are visible.",
    ),
    Selection(
        "09-elevated-junction",
        "playback",
        1418,
        1440,
        "Elevated roadside view shows a white work vehicle and light-colored sedan converging and colliding in the junction. Compilation repeats the moment with subtitles.",
    ),
    Selection(
        "10-night-junction",
        "playback",
        1552,
        1568,
        "Nighttime junction, vehicles crossing close together, followed by a curbside edited aftermath view. Bright headlights and low resolution limit detail.",
    ),
    Selection(
        "11-rain-highway",
        "playback",
        2446,
        2468,
        "Rain-obscured highway view shows a light sedan turning across lanes and stopping near the right side as the camera vehicle passes. The subsequent outcome is not shown.",
    ),
    Selection(
        "12-open-road-dust",
        "playback",
        2568,
        2602,
        "Open two-lane road, vehicle leaving the road amid a large dust cloud, then a damaged vehicle near the carriageway. A black editorial overlay obscures part of the aftermath.",
    ),
    Selection(
        "13-rear-camera-approach",
        "playback",
        3370,
        3386,
        "Rear-facing view of a white sedan approaching very close at a junction, followed by stationary close-up aftermath. Subtitle assertions about stop-sign behavior are unverified.",
    ),
    Selection(
        "14-box-truck-rollover",
        "playback",
        3400,
        3420,
        "Dashcam follows a pickup toward a junction; a white box truck tips onto its side while crossing ahead, followed by the camera vehicle passing the scene.",
    ),
]


def prepare(directory: Path, source: Path, selection: Selection) -> dict:
    output = directory / f"{selection.clip_id}.mp4"
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
            str(selection.start),
            "-i",
            str(source),
            "-t",
            str(selection.end - selection.start),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale='min(1280,iw)':-2",
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
        timeout=240,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-xerror",
            "-threads",
            "2",
            "-i",
            str(output),
            "-f",
            "null",
            "-",
        ],
        check=True,
        timeout=180,
    )
    details = inspect(output)
    if abs(details["duration_seconds"] - (selection.end - selection.start)) > 0.15:
        raise ValueError(f"Unexpected encoded duration: {output.name}")
    result = {
        "clip_id": selection.clip_id,
        "filename": output.name,
        "source_key": selection.source,
        "original_source_start": selection.start,
        "original_source_end": selection.end,
        "time_mapping": f"compilation_seconds = clip_seconds + {selection.start}",
        "review_notes": selection.notes,
        "full_decode_verified": True,
        "source_metadata": {
            "label": selection.clip_id.replace("-", " "),
            "recorded_by": "Original camera operator unknown",
            "location": "Not independently established; compilation overlays may give reported locations",
            "recorded_at": "Not independently established",
            "notes": f"Derived from {source.name}, compilation seconds {selection.start}–{selection.end}. {selection.notes} Compilation edits/replays are preserved. Offsets refer to the edited compilation, not a continuous real-world clock. All source assertions are unverified.",
        },
        **details,
    }
    print(f"Verified {output.name}: {details['duration_seconds']:.3f}s", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_directory",
        nargs="?",
        type=Path,
        default=Path.home() / "Downloads" / DEFAULT_DIRECTORY,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/additional-clips",
    )
    args = parser.parse_args()
    source_directory = args.input_directory.expanduser().resolve(strict=True)
    directory = args.output_dir.expanduser().resolve()
    paths = {key: source_directory / name for key, (name, _) in SOURCES.items()}
    originals = {key: inspect(path) for key, path in paths.items()}
    for key, (_, expected_hash) in SOURCES.items():
        if originals[key]["sha256"] != expected_hash:
            parser.error(f"Reviewed offsets do not belong to this source: {key}")
        spans = [item for item in SELECTIONS if item.source == key]
        if any(
            not 0 <= item.start < item.end <= originals[key]["duration_seconds"]
            for item in spans
        ):
            parser.error("A selected interval is outside its source")
        if any(a.end > b.start for a, b in pairwise(spans)):
            parser.error("Incident selections must not overlap")
    directory.mkdir(parents=True, exist_ok=True)
    if directory in {path.parent for path in paths.values()}:
        parser.error("Originals and generated clips must use separate directories")
    previous_path = directory / "manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        clips = list(
            pool.map(
                lambda item: prepare(directory, paths[item.source], item), SELECTIONS
            )
        )
    # Keep ingestion references only when the exact encoded bytes still match.
    for clip in clips:
        for old in previous.get("clips", []):
            if old.get("sha256") == clip["sha256"]:
                for key in ("ingested_case_id", "case_url"):
                    if key in old:
                        clip[key] = old[key]
    manifest = {
        "prepared_at": datetime.now(UTC).isoformat(),
        "originals_preserved": True,
        "sources": {
            key: {"path": str(paths[key]), **details}
            for key, details in originals.items()
        },
        "license": "Unknown; user-authorized local development use, no redistribution rights asserted.",
        "review_method": "All source footage covered by 10-second contact sheets (133 Tennessee frames, 368 playback frames); all 11 sheets visually inspected. Selected scenes refined with 2-second contact sheets and checked for unrelated scene boundaries. Sampling can miss brief events; this is not exhaustive frame-by-frame annotation.",
        "notice": "Each selection is a separate incident/interaction. Preserve each as its own case. Editorial replays, overlays, audio and camera-view cuts already present in each compilation remain; source clocks are edited compilation offsets, not real-world elapsed times. Labels are visual review notes, not verified fault, injury or causation findings.",
        "clip_count": len(clips),
        "clips": clips,
    }
    previous_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (directory / "verification.json").write_text(
        json.dumps(
            {
                "all_full_decodes_passed": True,
                "clip_count": len(clips),
                "clips": [
                    {
                        "filename": item["filename"],
                        "sha256": item["sha256"],
                        "duration_seconds": item["duration_seconds"],
                    }
                    for item in clips
                ],
            },
            indent=2,
        )
        + "\n"
    )
    rows = [
        "# Additional local test footage",
        "",
        manifest["notice"],
        "",
        "| Clip | Source | Original interval | Notes |",
        "|---|---|---:|---|",
    ]
    rows.extend(
        f"| [{item['filename']}]({item['filename']}) | {item['source_key']} | {item['original_source_start']}–{item['original_source_end']}s | {item['review_notes']} |"
        for item in clips
    )
    rows.extend(
        [
            "",
            "`manifest.json` records original paths, SHA-256 hashes, source clocks, reported metadata and ingested case IDs. `verification.json` records successful full decoding. Contact sheets are in `contact-sheets/`. The source recordings remain unchanged in Downloads.",
            "",
        ]
    )
    (directory / "README.md").write_text("\n".join(rows))
    print(f"Prepared {len(clips)} clips in {directory}")


if __name__ == "__main__":
    main()
