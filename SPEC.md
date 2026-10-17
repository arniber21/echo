# Rewind — Hackathon Spec

Turn scattered evidence (video, audio, photos) into an evidence-linked, navigable reconstruction of what happened. 5-hour demo build, laptop only, built by an agent swarm. Work is tracked in GitHub issues #1–#12.

## Scope

**In:** multi-file upload (video/audio/images), AI event extraction, merged timeline, evidence linking, click-to-seek playback, incident summary, missing-evidence checklist, contradiction detection, printable report.

**Out:** chat with evidence, 3D reconstruction, legal fault determination, real-time video analysis, hosted deployment, server-side PDF.

**Hard rule:** the app organizes evidence and states what can and cannot be established. It never determines fault, and never presents an inference as verified.

## Demo scenario

Minor vehicle collision. Upload a 15–30s dashcam clip (audible impact), 2–3 damage photos, and a 20–40s voice memo containing one detail that conflicts with or is absent from the video. Click Analyze, inspect the timeline, click an event to seek the video, view a missing-evidence item, open the report.

## Stack

- Backend: Python, FastAPI, managed with `uv`
- Frontend: bun + TanStack
- AI: Gemini (single multimodal provider, video/audio/images natively). `GEMINI_API_KEY` and `GEMINI_MODEL` (Flash-class default) in `backend/.env`; ship `.env.example`
- Storage: SQLite (`cases`, `media_files`, `jobs`; analysis stored as a JSON column on the case). Original media on disk under gitignored `data/`
- Run: `make demo` starts both servers. No deployment.
- FFmpeg only if needed (poster frames, transcoding for playback)

## Contract

Pydantic models are the single source of truth; TypeScript types are generated from them. `sample_case.json` is the fixture all tracks build against; a mock Gemini client returns fixture-shaped output until the key exists.

### Event

| Field | Meaning |
|---|---|
| `event_id`, `title`, `description` | Identity and text |
| `source_id`, `source_type` | Originating file; video / audio / photo |
| `source_start`, `source_end` | Exact time in the source's own file. **Used for seeking.** |
| `case_min`, `case_best`, `case_max` | Estimated placement on the merged axis |
| `alignment_basis`, `alignment_confidence` | Why and how sure the placement is |
| `confidence`, `verification_status` | Model confidence; always `unverified` from AI |
| `evidence_type` | `observation`, `inference`, or `testimony` |
| `supports[]` | Event ids a photo supports |

### Case-level outputs

`summary` (factual, every claim source-referenced), `missing_evidence[]`, `contradictions[]` (each links both conflicting sources).

## Timeline model

- Single merged timeline. **Case clock = video clock** (t=0 is video start).
- Video events: tight ranges (about ±0.5s).
- Audio statements: Gemini matches them to video events by content; range narrows with match strength; no match means a wide range with low confidence. One-line `alignment_basis` shown on hover.
- Photos: EXIF time if present; otherwise an open-ended range after the impact, labeled "post-incident, time unknown". Photos link to events via `supports[]`.
- Rendering: range bar, best-guess dot, "estimated" badge. Observations and inferences are visually distinct.

## Analyze pipeline

`POST analyze` starts a background job: uploading → analyzing video → analyzing audio → synthesizing. The frontend polls status.

1. Per-file extraction (strict-JSON output, schema-validated, one retry on invalid output).
2. Photo analysis.
3. One synthesis call: merges onto the case clock, writes summary, missing evidence, contradictions.
4. Results cached on disk by file hash, so re-running on the same files needs no API call (this is the on-stage fallback).

## Acceptance criteria

| Criterion | Done when |
|---|---|
| Multimodal | At least one video, one audio, one photo processed |
| Accuracy | Key events trace to identifiable source evidence |
| Interactivity | Clicking a video event sets player `currentTime` equal to its `source_start` |
| Reliability | Full demo completes with no manual intervention |
| Polish | Clean UI, progress indicators, useful errors, consistent design |

## Risks

| Risk | Mitigation |
|---|---|
| AI invents details | Require source references; label inference vs observation |
| Timestamps don't align | Ranges plus explicit `alignment_basis` |
| API fails on stage | Cached analysis and a committed pre-analyzed demo case |
| Slow video analysis | 15–30s clips |
| Privacy | Synthetic or consented media; local storage only; Gemini is the sole external transfer |
| Swarm pieces don't fit | Contract-first (#1); everything builds against the fixture |

## Build order

#1 contract and skeleton → #3 upload, #4 timeline (parallel) → #5 analyze job with mock → #6–#8 real Gemini extraction, photos, synthesis → #9 checklist and contradictions, #10 report, #11 fallback (parallel) → #12 verification and polish. #2 (media and key) is a human task that runs alongside.
