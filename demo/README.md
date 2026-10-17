# Synthetic demonstration evidence

All files in `media/` were generated specifically for this repository. They depict
no real people, vehicles, or incident. They are deliberately committed for offline
rehearsal. User-uploaded evidence is stored in gitignored `data/`.

- `demo-video.mp4`: 20-second overhead illustration. Amber car A approaches stationary
  teal car B. Contact and an audible impact occur at video time 8 seconds. The
  illustrated signal is red throughout. This is a schematic, not dashcam footage.
- `demo-audio.m4a`: approximately 21-second synthetic witness narration. The narrator
  remembers a green signal at contact, intentionally conflicting with the video.
- `demo-photo-front.jpg`: illustration of damage at car A's front bumper.
- `demo-photo-side.jpg`: illustration of damage at car B's rear bumper.
- `poster.jpg`: illustrative video preview. Not an additional evidence source.

Neither damage illustration contains EXIF capture time. Their placement must remain
open-ended and labeled “post-incident, time unknown.”

The committed `shared/sample_case.json` contains prewritten analysis for these exact
illustrations. It is a transparent demonstration fixture, not Gemini output.
Gemini's live outputs vary and must be judged against the actual source files.

To regenerate the binaries on macOS: install Pillow, FFmpeg, and the Samantha system
voice, then run `python3 scripts/generate_demo.py`. The application only needs the
already-generated files; macOS speech synthesis is not a runtime dependency.

Narration:

> This is a synthetic witness statement for the Rewind demo. I was in the amber car
> approaching the teal car ahead of me. I remember that the traffic signal was green
> when the cars made contact. I heard a short bump and both vehicles stayed in the
> same lane. Afterwards I noticed damage to the front of the amber car. I cannot
> remember the exact speed, and I did not see anyone get hurt.
