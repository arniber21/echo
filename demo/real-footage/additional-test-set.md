# Additional local footage

Fourteen reviewed scenes from the two recordings in the user-provided `Downloads/drive-download-20261017T194907Z-1-001` directory. Both originals remain unchanged. The Tennessee compilation lasts 1,333.754 seconds (22m14s); `videoplayback.mp4` lasts 3,678.598 seconds (61m19s).

The prepared files live in ignored `data/additional-clips/`. The running local API received one clip per new case: **14 additional cases**, each with reported source metadata, original compilation offsets, and notes distinguishing visible activity from subtitle claims. Existing cases were preserved. Ingestion does not request analysis or incur model calls. Case IDs and frontend URLs are recorded in the local manifest rather than committed because they belong to this database.

| File | Source | Original seconds | Review notes |
|---|---|---:|---|
| 01-mountain-road.mp4 | Tennessee | 14–38 | Wooded road, then edited roadside damage footage |
| 02-tree-lined-road.mp4 | Tennessee | 498–520 | Camera displacement toward vegetation; original includes replay |
| 03-truck-side-views.mp4 | Tennessee | 578–630 | Close tractor-trailer pass; multiple original views/replays and damage still |
| 04-junction-airbag.mp4 | Tennessee | 740–770 | Crossing traffic, obscured camera, inserted damage photographs |
| 05-motorcycle-interaction.mp4 | Tennessee | 846–922 | Motorcycle/hatchback interaction; no collision visible in reviewed frames |
| 06-cloudy-box-truck.mp4 | Tennessee | 1174–1188 | Truck enters ahead; near-miss candidate without visible contact |
| 07-bridge-close-pass.mp4 | Playback | 0–26 | Silver car close pass, with original replay |
| 08-dusk-junction.mp4 | Playback | 612–632 | Crossing collision and dust/smoke |
| 09-elevated-junction.mp4 | Playback | 1418–1440 | Elevated view of work vehicle/sedan collision and replay |
| 10-night-junction.mp4 | Playback | 1552–1568 | Headlight-obscured junction incident and edited curbside view |
| 11-rain-highway.mp4 | Playback | 2446–2468 | Rain-obscured sedan turns across lanes; later outcome absent |
| 12-open-road-dust.mp4 | Playback | 2568–2602 | Vehicle leaves road, dust cloud and obscured aftermath |
| 13-rear-camera-approach.mp4 | Playback | 3370–3386 | White sedan approaches very close behind; stationary aftermath |
| 14-box-truck-rollover.mp4 | Playback | 3400–3420 | Box truck tips onto its side crossing a junction |

## Review and limitations

All 83.5 minutes were covered by ten-second contact-sheet sampling: 133 Tennessee frames and 368 playback frames, across eleven sheets. Every sheet was visually reviewed. Selected scenes were then inspected at two-second spacing to exclude unrelated neighboring scenes. This is sampled visual review, not exhaustive frame annotation; brief events can be missed. Contact sheets are retained locally.

The originals already contain editorial cuts, replays, graphics and spoken claims. Those remain in the clips. Offset mappings refer to **edited compilation time**, not continuous real-world time. Replayed frames must not become duplicate timeline incidents. Different scenes are separate cases, not corroborating viewpoints. Subtitle assertions about fault, injuries, intoxication, insurance and locations are not independently established. The no-visible-collision scenes are useful negative or ambiguous examples for evaluation.

Every derived clip is browser-playable H.264/AAC with `faststart` and YUV420P. Low-resolution material remains 640×360 instead of being upscaled; the Tennessee source is downscaled to 1280×720. Each clip passed FFprobe, duration checks and full FFmpeg decoding with error escalation. The manifest records original and output SHA-256 hashes, byte sizes, streams, offsets, metadata, and ingestion references. `verification.json` records decode checks.

No redistribution rights are asserted. Sources and prepared media stay outside Git.

## Reproduce

From the main checkout:

```sh
devbox run -- just prepare-additional-clips
devbox run -- just ingest-additional-clips
```

The preparation script checks pinned source hashes before using these reviewed offsets. The ingestion script checks every clip hash, creates a separate case per clip, and saves case IDs after each successful upload. Re-running ingestion reuses a case only when its exact title and media hash match; it does not overwrite or delete any case. After an ambiguous failed upload, re-run ingestion so it checks the current case list before attempting another POST.

The API must be running at `http://127.0.0.1:8000`. An alternate local URL can be passed to `scripts/ingest_prepared_clips.py` with `--base-url`. The script does not trigger analysis. Open a case via its manifest URL and click **Analyze evidence** when ready.
