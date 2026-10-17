# Audio extraction grounding — issue #32

The affected 25-second `van-incident-audio.m4a` upload contains one AAC audio
stream and no video stream. Its persisted extraction nevertheless described a
camera dropping, parked vehicles and pavement. Those visual observations cannot
come from this input.

Inspection found no source routing mismatch: the uploaded SHA-256 matches the
prepared artifact manifest, the extraction pipeline passes that source's exact
path with `audio/mp4`, and provider upload includes that MIME type. The prepared
audio and full video's decoded mono 16 kHz tracks have matching duration and a
0.99967 correlation between 100 ms energy windows. This supports their common
recording origin; it is not a general synchronization algorithm.

The old extraction policy included video and photo instructions even for audio.
The replacement sends only the selected modality's instructions. Audio forbids
visual descriptions and guessing unclear language or words, distinguishes sounds
from their possible physical causes, and permits an empty extraction. The
extraction policy version changes so old cached hallucinations are not reused on
the next analysis. Existing accepted case analyses remain intact until reanalysis.

## Live verification, 2026-10-17

Three standalone calls used the actual uploaded bytes or their decoded WAV,
`gemini-3.8-flash`, temperature zero, and the production provider. They did not
write to the case database.

| Input/policy | Result |
| --- | --- |
| Original M4A, old policy | No visual claims in this replay; German exclamation and vehicle/impact sounds |
| Original M4A, modality-specific policy | No visual claims or definite transcription; breathing, scuffle and exclamation |
| Decoded WAV, modality-specific policy | No visual claims; clattering and a different, explicitly uncertain transcription |

The revised policy removed visual fabrication in these two trials. Acoustic
interpretations remained inconsistent, including language. This is **not** proof
of reliable transcription or timing. Prompt changes alone do not establish
accuracy, and changing the container did not resolve the inconsistency. Do not
present uncertain language differences as established contradictions or use them
as precise synchronization anchors. Broader live evaluation remains in #13.

The focused automated regression checks source isolation and that the new policy
bypasses the old extraction cache. Its simulated model does not measure acoustic
accuracy. No fragile keyword filter is used to declare prose acoustically valid.
