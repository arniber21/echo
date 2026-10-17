# Rewind implementation agreement

The user has authorized implementation, parallel subagents in isolated Git worktrees,
and merges directly into main. Use Nuxt UI with Nuxt/Vue and strict TypeScript in
place of the original TanStack frontend. Backend is FastAPI/Pydantic/SQLite via uv.

## Shared boundaries

- `backend/rewind/models.py` owns the contract. Generated schema lives at
  `shared/schema.json`; generated TypeScript at `frontend/app/types/generated.ts`.
- `shared/sample_case.json` is the canonical, explicitly synthetic demo fixture.
- All API routes use `/api`. Media URLs are relative `/api/media/{id}`.
- `GET /api/health`, `GET /api/cases`, `GET /api/cases/demo`,
  `GET /api/workspace` (locally selected default case),
  `POST /api/cases` (multipart `files`, optional `title`),
  `POST /api/cases/{id}/media` (append multipart evidence),
  `PATCH /api/cases/{id}/media/{source_id}` (reported source context),
  `GET /api/cases/{id}`, `POST /api/cases/{id}/analyze`,
  `GET /api/jobs/{id}`, `GET /api/media/{id}`.
- Case has `case_id`, `title`, `created_at`, `media_files`, `analysis` (nullable).
- Media has `source_id`, `filename`, `source_type` (video/audio/photo),
  `mime_type`, `url`, `sha256`, `duration_seconds` (nullable),
  `captured_at` (nullable). Backend may add size fields.
- Analysis has `events`, `summary` (array of `{text, source_refs}`),
  `missing_evidence` (array of `{id, title, description, source_refs}`),
  `contradictions` (array of `{id, title, description, source_refs}`).
- SourceRef has `source_id`, `source_start`, `source_end` (times nullable for photos).
- Event has the SPEC.md fields; `case_min`/`case_max` are nullable for open ends;
  `case_best` is numeric; photo source times are nullable; verification_status is
  always `unverified`. `supports` defaults to an empty list.
- Job has `job_id`, `case_id`, `status` (queued/running/completed/failed),
  `stage` (uploading/analyzing_video/analyzing_audio/analyzing_photos/synthesizing/completed/failed),
  `progress` (0..100), `error` (nullable).
- Analyze defaults to mock with no key, live with key; explicit configuration can
  force mock. Mock results must disclose simulated analysis and use actual file IDs.
- Keep source clocks distinct from case placement. Validate all references and
  ranges. Never present AI claims as verified or determine fault.

## Engineering standards

Use cohesive modules with explicit boundaries; generated types are never edited by
hand. Vue components own presentation, composables own async state and polling,
and pure utilities own timeline calculations. No `any`, unchecked casts, or large
monolithic page components. Meaningful tests cover data integrity, upload safety,
retry/caching behavior, source seeking, and full demo flow. Document assumptions.

## Ownership

Backend agent: backend contract, persistence, upload, routes, jobs, backend tests.
Frontend agent: Nuxt UI app and frontend unit checks.
AI agent: provider/extraction/synthesis/cache modules and related tests.
Root: integration, demo assets, launcher/docs, browser verification, final review.

## Evolving reconstructions and working account

Cases advance `evidence_revision` on each evidence batch. Analysis is committed
against one revision with the exact analyzed source IDs, timestamp, and prior
completed reconstruction snapshots. New evidence preserves the old analysis and
marks it stale. A case lock prevents evidence mutation during analysis.

`Case.memory` is a materialized working account projected from validated analysis
at commit time. It stores content-addressed summary/observation/testimony/inference/
question/conflict entries with source references and revision lifetimes. Unchanged
entries share identity; replaced entries are superseded and retained. Reads and
uploads do not regenerate memory, and projection does not call the model.

Extraction and synthesis have separate prompt/cache versions. An additional source
reuses prior file extractions while synthesis considers the complete current set.
Previous model summaries are never treated as established evidence for synthesis.

Source annotations are typed `SourceMetadata` values: label, recorder, location,
reported recording time, and notes. Uploads accept an ordered metadata JSON array.
Edits preserve file hashes and seek clocks, increment the evidence revision, and
retain prior metadata in completed reconstruction snapshots. Synthesis consumes
annotations as untrusted reported context; they never replace EXIF or source time.
