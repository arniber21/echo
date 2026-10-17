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
  `POST /api/cases` (multipart `files`, optional `title`),
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
