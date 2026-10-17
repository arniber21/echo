# Video comparisons

Multi-video analysis uses Jev first to classify pairs as the same footage, the same
incident from different cameras, different incidents, or uncertain. It compares
sampled images and extracted observations. Filenames and user notes cannot establish
incident identity. Exact duplicate bytes require no model request.

The comparison budget is six deterministic pairs against a primary anchor. This is
not an exhaustive comparison of every possible pair. Coverage limits are recorded
in diagnostics, and every original source remains available.

Up to two plausible uncertain pairs receive a detailed Gemini review using a
labelled contact sheet and source observations. Each review has a 60-second deadline
and a content/model/prompt cache. Failure leaves the initial Jev assessment intact
and does not prevent reconstruction. The detailed result is stored separately;
the UI retains the initial probabilities rather than replacing them.

An event match requires a distinctive shared action. Ordinary driving or the
presence of a similar vehicle cannot establish a common instant. Proposed detailed
event matches also receive a Jev text check; uncertain or failed checks remove the
match. Reference validation requires an observation from each corresponding source.

Separate [content matching](content-alignment.md) can locate excerpts or copied
audio inside a primary recording; it does not synchronize independent cameras.

The synthesis receives these provisional assessments so viewpoint differences
alone need not become contradictions. They are not proof of identity. Each source
retains its own clock, and the comparison does not calculate a clock offset.
Candidate-event buttons seek the corresponding source time. Case-clock placement
continues to carry explicit uncertainty.

Local live smoke checks recognized an unrelated mountain-road control as a different
incident and escalated an uncertain front/side camera pair to detailed review.
These are individual checks, not an accuracy benchmark. Full-versus-spliced accuracy,
false matches, cost, and latency remain tracked in [eval #13](https://github.com/arniber21/echo/issues/13).
