# User-provided local intersection incident

This case comes from the user's local compilation, not from the synthetic demo.
The original is read-only input and remains in Downloads. Large originals and all
derived media stay in ignored `data/footage/local-intersection/`.

## Selection

- **Original filename:** `Accidents at intersections compilation Cars Accidents - Cars Accidents (1080p).mp4`.
- **Original duration:** 823.100952 seconds; 1920×1080; video and audio present.
- **Original size:** 388,064,269 bytes.
- **Selected original interval:** 123–139 seconds.
- **Main output:** `data/footage/local-intersection/incident.mp4`, measured 16.016 seconds, 1280×720, approximately 2.24 MB.
- **Original time mapping:** `original_seconds = incident_seconds + 123`.
- **Apparent contact:** approximately original 131–133 seconds, or clip 8–10 seconds, based on manual contact-sheet review. This is a rough test annotation, not a verified impact timestamp.

A stationary camera observes crossing traffic at an intersection. Two vehicles
make apparent contact, with visible debris or dust and a short aftermath. The
chosen interval retains the approach and aftermath while excluding adjacent
compilation incidents. It contains one continuous camera angle. No graphic injury
appears in the reviewed frames; medical condition cannot be established from
this selection.

The compilation includes channel/vehicle graphics. These remain visible. The
uploader, original camera owner, incident location, rights holder and license are
not established from the local filename. This is user-authorized local development
material; no redistribution license or independent source attribution is asserted.
No downloaded YouTube copy or replacement footage is used.

## Reproduce

Within the project's devbox environment, using Python 3.11+ and FFmpeg:

```sh
uv run --project backend python scripts/prepare_local_incident.py \
  --start 123 --duration 16 --with-derivatives
```

The input defaults to the above filename under `Path.home() / "Downloads"`.
For any other local recording, pass its path explicitly:

```sh
uv run --project backend python scripts/prepare_local_incident.py \
  /path/to/recording.mp4 --start 123 --duration 16
```

The script validates source duration and source/output path separation, hashes
the original without copying it, and writes a provenance manifest containing the
original path, exact SHA-256, streams, byte count, selection offsets and each
artifact's own hash. It transcodes a contiguous slice to H.264/AAC for browser
playback without rearranging frames. Codec packet padding can add approximately
one frame to measured duration.

`--with-derivatives` additionally writes temporal-third fragments `before.mp4`,
`impact.mp4` and `after.mp4`, the recording's true extracted audio, and frames at
20% and 80% of the selected interval. Fragment labels are convenient test names;
they do not automatically establish an event timestamp. The source offsets are
recorded in `manifest.json`.

All derived audio, stills and fragments come from this **one recording**. They
are not independent witnesses, testimony, separate camera angles, or independent
damage photographs. Use `incident.mp4` alone as the initial evidence upload. Add
other derivatives only to test media handling with their common origin disclosed.
