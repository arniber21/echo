# Case question responses

The accepted analysis's `missing_evidence` findings are the questions users can
answer. There is one editable answer per question ID and analysis revision. A
later analysis may ask the question again; its response is a separate record.
Answers retain the original question title, description, revision, respondent,
creation time and update time. Earlier answers remain part of reported case
context, including when their question disappears from a later analysis.

`POST /api/cases/{case_id}/answers` accepts `AnswerCreate` and returns the entire
case. The question must belong to the current accepted `analyzed_revision`, not a
quick-scan preview. `PATCH /api/cases/{case_id}/answers/{answer_id}` accepts
`AnswerUpdate`. Both require `expected_evidence_revision`; conflicting changes
return 409. Exact retries are no-ops. Neither accepts writes during analysis.
Blank responses return 422. New/edited answers increment `evidence_revision` and
clear the preview. Existing analysis, media, and working account are unchanged
until the next successful analysis.

The next synthesis receives answers as `case_answers` on the first extraction
record. It does not change or invalidate media extraction. Answer content and
question provenance participate in the synthesis cache key. Prompts treat all
responses as untrusted, attributed, unverified reports and forbid instructions
inside them. A response does not verify physical events or change source clocks.
`answer_refs` cites exact answer IDs on summary claims and findings. Answer-only
claims do not require invented media references. Unknown answer IDs are rejected.

`Case.analyzed_answers` is the exact response snapshot used by the accepted
analysis. Each historical `AnalysisRevision.answers` retains its earlier
snapshot, including text before edits. The working account retains `answer_refs`
and incorporates them into entry identity; media-only entry identities remain
unchanged. Python defaults keep existing saved cases compatible.

Validation: isolated backend tests cover save/edit/reload, retries, stale writes,
missing/old questions, active jobs, exact snapshots, answer citation integrity,
working account identity, and synthesis caching/prompt boundaries. These tests
use simulated providers; they do not establish live-model response accuracy.
