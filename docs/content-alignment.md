# Content-based timeline alignment

New reconstructions use the longest video as their primary clock, breaking duration
ties by content hash. The accepted analysis stores `clock_source_id`. Earlier
reports without that field retain their original hash-selected clock; adding a file
does not silently relabel an accepted or historical reconstruction.

Before synthesis, a local matcher searches for unchanged or re-encoded excerpts
inside the primary recording. Five separated low-resolution frames must agree on
one unit-speed offset. Competing locations, nearly static excerpts, low-information
frames, and inconsistent temporal matches are rejected. Still images need a unique
pixel match. Audio uses an energy fingerprint with high whole-track correlation,
three segment checks, and ambiguity rejection. None of these operations uses a
filename, source preparation manifest, geolocation, or model assertion.

For supported matches, code applies `case_time = source_time + offset`; the model
cannot alter the measured mapping. Video/still uncertainty is ±0.5 seconds; matched
audio uncertainty is ±0.2 seconds. These describe the matching procedure's sampling
window, not the accuracy of a model-extracted event boundary. Quality scores are
heuristics, not calibrated probabilities. Source seek timestamps remain unchanged.

Matching is bounded to twelve sources and 300 seconds per recording, with small
cached descriptors and decoder deadlines. Longer sources still anchor their own
events, but secondary matching remains unavailable. The algorithm handles contained
excerpts, not arbitrary edits, speed changes, or independent camera viewpoints.
Missing matches remain unknown; they do not prove unrelated incidents.

Unknown case placements appear as source-time cards rather than full-width case
bars with an artificial dot at zero. A supported partial bound can still use an
open-ended range.

## Verification

The reported seven-source case matched before/impact/after excerpts at 0/2/7 seconds
and its copied audio at zero. One still matched at 2 seconds; the other remained
ambiguous. Actual-byte matching took about one second uncached for the visual pass.

Without changing thresholds, four additional real incidents were used to make
re-encoded eight-second excerpts at 3.25, 4.5, 2, and 6.75 seconds. All four offsets
were recovered exactly on the sampled grid. Eight unrelated video comparisons and
replayed/static controls were rejected. Two of four additional stills matched within
0.25 seconds; two stayed unknown. These small checks support same-recording matching;
they do not establish general accident interpretation or transcription accuracy.
The broader human-labelled evaluation remains [#13](https://github.com/arniber21/echo/issues/13).
