# Real dashcam test footage

The downloaded files live in ignored `data/footage/`; the committed synthetic demo
stays separate. Reproduce with the devbox toolchain:

```sh
python scripts/prepare_dashcam.py
```

The script downloads at most 50 MiB, verifies a pinned original SHA-256, preserves
the original file, and creates contiguous H.264/AAC slices. It requires Python 3.11+
and FFmpeg/ffprobe, available through the project's devbox configuration.

## Source and attribution

- **Title:** The van in front suddenly changed lanes and caused the vehicle to rear-end collision.webm.
- **Repository:** [Wikimedia Commons source and licensing page](https://commons.wikimedia.org/wiki/File:The_van_in_front_suddenly_changed_lanes_and_caused_the_vehicle_to_rear-end_collision.webm).
- **Exact source revision:** [revision 1198533330](https://commons.wikimedia.org/w/index.php?title=File:The_van_in_front_suddenly_changed_lanes_and_caused_the_vehicle_to_rear-end_collision.webm&oldid=1198533330).
- **Original binary:** [downloadable WebM](https://upload.wikimedia.org/wikipedia/commons/7/79/The_van_in_front_suddenly_changed_lanes_and_caused_the_vehicle_to_rear-end_collision.webm).
- **Upstream source listed by Commons:** [Douyin video 7463173675475291450](https://www.douyin.com/video/7463173675475291450).
- **Commons uploader:** Fumikas Sagisavas, 11 February 2025; original author is not identified by Commons. Uploader is not represented as the camera owner.
- **Date displayed by camera:** 2025-01-23. Commons description lists 23 January 2025.
- **Retrieved:** 17 October 2026.
- **Original:** 48.026 seconds, 1280×720, VP9/Opus, 19,725,940 bytes.
- **Original SHA-256:** `73dda42943020ca582f2b2d7c9c054135e3158a1c3bab4ad2092d6acba31293a`.

Commons declares this file public domain under **PD-automated**. This is the
repository's declaration, not an owner-issued Creative Commons license. The
source page itself notes that copyright treatment of automated recordings varies
by jurisdiction. The files are retained as local development data, outside Git;
no broader redistribution permission is asserted. The source title is preserved
for attribution and is not adopted as a verified causation or fault finding.

Web searches also checked YouTube Creative Commons results. Ordinary YouTube
availability did not establish a downloadable reuse license. A Florida police
[dashcam of a small-plane road landing](https://commons.wikimedia.org/wiki/File:Police_Dashcam_Captures_Small_Plane_Crashing_Onto_Florida_Road.webm)
had a stronger PD-Florida declaration, but did not match the requested car-contact
scenario. An ND-licensed accident sample dataset was excluded from splicing.

## Prepared artifacts

| File | Original interval | Use |
|---|---|---|
| `van-rear-end-original.webm` | 0–48.026 s | Preserved original |
| `van-incident.mp4` | 0–25 s | Main incident upload, approximately 3.7 MB |
| `van-before.mp4` | 0–3 s | Short approach fragment |
| `van-impact.mp4` | 2–7 s | Contact fragment; original time = clip time + 2 s |
| `van-after.mp4` | 7–22 s | Aftermath fragment; original time = clip time + 7 s |
| `van-incident-audio.m4a` | 0–25 s | Original recording's extracted audio |
| `van-before-frame.jpg` | 2 s | Frame extracted from original video |
| `van-after-frame.jpg` | 8 s | Frame extracted from original video |

`manifest.json` records exact measured durations, byte counts, hashes, and source
offsets for every generated artifact. Video and audio are transcoded; no frames
are rearranged and no unrelated footage is joined. All video variants retain
chronological order and their original source offset in the manifest.

Manual frame review places apparent vehicle contact around original time 3–4 s.
This is an approximate test annotation, not a verified impact timestamp. A van
moves across the recording vehicle's forward view; a white vehicle becomes close
to the camera, the image jolts, and the recording vehicle remains stationary for
much of the aftermath. No graphic injury is visible in the reviewed frames;
the recording does not establish anyone's medical condition.

The extracted audio and stills are derivatives of the **same recording**. They
are not independent corroboration, witness testimony, or independent damage
photographs. Avoid uploading the original plus every derivative as though they
were distinct witnesses. Use `van-incident.mp4` alone for video analysis; use
individual fragments for truncation tests, or a clearly described combined case
to exercise multi-video alignment. A multimodal plumbing test may use the main
clip, extracted audio and stills with this common provenance disclosed.
