# Full-compilation intersection test set

Fifteen distinct incident clips are prepared in **`data/test-clips/`**. The folder
contains numbered MP4s, a clickable `README.md` upload guide, `manifest.json`,
`verification.json`, and visual review sheets under `contact-sheets/`.

The input is the user-provided local file
`Downloads/Accidents at intersections compilation Cars Accidents - Cars Accidents (1080p).mp4`.
Its measured duration is **823.100952 seconds: 13 minutes 43 seconds**. The original
388,064,269-byte recording was read without alteration or copying into Git. Its
SHA-256 is
`f82bfedc289fac33b38c9fc88f36c69bc8a12901663b8d53572e03285c8c256f`.

## Review coverage and selection

Review covered the entire 0–823.101-second source using coarse eight-second and
then dense two-second contact sheets. All eleven dense sheets were inspected,
including the final incident and the outro. FFmpeg scene-change candidates at a
score above 0.35 helped refine boundaries; abrupt collision motion can also
trigger that detector, so candidates were checked visually rather than treated
as authoritative cuts. Representative approach, contact-window and aftermath
frames from every selected clip were reviewed again after encoding.

The chosen incidents span original source seconds **9–815**. No unrelated
compilation scenes are joined or used as padding. Nine clips last at least
15 seconds, five retain original scenes lasting 10–14 seconds, and the final
incident retains its actual approximately eight-second scene before the outro.
The shorter originals are documented rather than extended with another crash.

| Clip | Source interval | Measured duration | Scene |
|---|---:|---:|---|
| `01-suv-crossing.mp4` | 9–27 s | 18.001 s | Dark vehicles at a signal junction |
| `02-overcast-junction.mp4` | 77–100.8 s | 23.807 s | Overcast junction and a tipping white van |
| `03-cross-traffic-contact.mp4` | 123–139 s | 16.016 s | Crossing cars, contact and debris |
| `04-police-car-contact.mp4` | 184.7–203.1 s | 18.402 s | Police-marked vehicle crossing close to the camera |
| `05-tree-lined-crossing.mp4` | 275.2–290.9 s | 15.716 s | Crossing near trees and pedestrian railings |
| `06-white-car-turning.mp4` | 291.4–304.5 s | 13.113 s | White car and dark SUV near a water tower |
| `07-intersection-rollover.mp4` | 337.6–357.2 s | 19.603 s | Crossing contact followed by an overturn |
| `08-dusk-truck-crossing.mp4` | 518.6–531.2 s | 12.613 s | Truck crossing followed by smaller-vehicle contact |
| `09-urban-car-contact.mp4` | 562.9–576.4 s | 13.514 s | Urban collision with a passing bus |
| `10-night-overhead.mp4` | 613–624.6 s | 11.612 s | Elevated nighttime view |
| `11-open-road-mini.mp4` | 654.4–670.9 s | 16.517 s | Red compact car at an open-road junction |
| `12-city-close-impact.mp4` | 727.9–738.3 s | 10.410 s | Close city-street collision |
| `13-wet-road-impact.mp4` | 747.8–766.7 s | 18.902 s | Wet-road collision and obscured windshield |
| `14-ramp-junction.mp4` | 783.9–806.7 s | 22.806 s | Signal junction near a ramp |
| `15-final-overhead.mp4` | 807.2–815 s | 7.808 s | Final elevated-camera incident before the outro |

Descriptions and contact windows are approximate review annotations. They are
not verified findings about fault, speed, signal violations, location, or injury.
No graphic injury is visible in the reviewed frames; medical outcomes cannot be
established from these selections. Some clips include overturns or substantial
vehicle damage. Source captions remain visible and are not adopted as findings.

## Reproduce and inspect

With the project devbox environment active:

```sh
uv run --project backend python scripts/prepare_local_test_set.py
```

The script defaults to the named file under `Path.home() / "Downloads"`. A
positional input path and `--output-dir` can override those locations. The original
SHA-256 must match the reviewed compilation before any output is written.
Encoding uses at most two FFmpeg processes, each limited to two codec threads,
and produces H.264/AAC MP4s with browser-friendly startup metadata. No Gemini
request, upload, or application database write occurs during preparation.

For review sheets, the full-film scan used:

```sh
ffmpeg -threads 2 -i /path/to/original.mp4 \
  -vf 'fps=1/2,scale=320:-1,tile=5x8' -fps_mode vfr \
  /path/to/review/sheet-%02d.jpg
```

The prepared folder retains eleven full-source sheets with approximate source
second labels and three selected-clip sheets showing five clips each. Encoding
verification fully decoded all fifteen MP4s, checked their H.264/AAC streams,
matched every SHA-256 to the manifest, and confirmed that the intervals do not
overlap. Total clip size is approximately **40.3 MB**, with **238.84 seconds** of
selected footage. Codec packet padding accounts for small differences between
requested and measured durations.

## Manifest and upload use

`manifest.json` contains `source_path`, `source_filename`, `source_original`
(duration, byte count, hash and streams), `scan_coverage`, `clip_count`, and `clips`.
Each clip records:

- `clip_id`, `filename`, `duration_seconds`, `size_bytes`, `sha256`, and `streams`.
- `original_source_start` and `original_source_end`, with the explicit mapping
  `original_seconds = clip_seconds + original_source_start`.
- Approximate contact ranges in both original and clip clocks.
- Review notes, any short-scene explanation, and a `source_metadata` object ready
  for the app's five annotation fields.

Upload **one numbered clip per new reconstruction**. These are distinct
incidents, not independent witnesses to one collision. Every clip resets its
source clock to zero. Metadata is explicitly user-reported and unverified; the
original operator, recording time and precise location have not been established.
No unrelated voice testimony, sound effects, or independent damage photographs
have been added.

The original compilation's license and rights holder are unknown from the local
file. This is user-authorized local test data; no redistribution permission is
asserted. All source media, derivatives, manifests and review images remain
outside Git under the ignored data directory.
