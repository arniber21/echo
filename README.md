# Rewind

An evidence workspace for reconstructing an incident from video, audio, and images.
Upload media, analyze it with Gemini, and inspect a source-linked timeline, summary,
missing evidence, and conflicting accounts. Every AI finding remains unverified.

Built with FastAPI, Pydantic, SQLite, Nuxt, Vue, and Nuxt UI. Pydantic models generate
the shared JSON schema and TypeScript contracts. The frontend uses focused Vue
components, typed composables, and pure timeline utilities.

## Run locally

Install [Devbox](https://www.jetify.com/docs/devbox/installing_devbox/), then:

```sh
devbox install
devbox shell
just setup
just demo
```

Open **http://127.0.0.1:3000**. API documentation is at
**http://127.0.0.1:8000/docs**. Ctrl-C stops both servers. The launcher checks for
occupied ports instead of silently choosing different ones. Set `REWIND_API_PORT`
and `REWIND_WEB_PORT` to override them.

Devbox pins Python, Node, Bun, uv, just, and FFmpeg. `uv.lock` and `bun.lock` pin
application dependencies. Tasks also run without entering a shell:
`devbox run -- just check`.

The workspace starts empty. Upload files to create a case; later visits open the
selected or most recent case. Sample cases are never inserted during normal startup.
Original evidence, analysis, history, and preferences live under gitignored `data/`.

To prepare and open that case on another machine, run the local splice script with
your source path, then import its output through the API:

```sh
uv run --project backend python scripts/prepare_local_incident.py '/path/to/compilation.mp4' --start 123 --duration 16
uv run --project backend python scripts/import_case.py data/footage/local-intersection/incident.mp4 --title 'Intersection incident' --analyze live --default
```

Start `just demo` before importing. The original video is never modified. A bundled
synthetic fixture is used only by the isolated browser tests. Explicit manual
fixture seeding requires `REWIND_SEED_DEMO=true`; it is disabled by default.
See [fixture details](demo/README.md) and [local clip provenance](demo/real-footage/local-incident.md).

## Build a case over time

Use **Add footage & files** in the main menu or evidence library to attach sources
to the current case. **New case** starts a separate reconstruction. Intake supports
multiple files, drag and drop, and optional per-file labels, recorder, location,
reported recording time, and notes. These can also be edited later through
**Edit details**. Reported context stays separate from file-derived metadata.

Start a new case with one video and analyze it. **Add footage & files** attaches further
photos, audio, or clips to that same case. The previous reconstruction stays
visible, explicitly marked as awaiting new evidence, until **Update reconstruction**
completes. Existing extraction caches are reused; synthesis incorporates the new
evidence and may revise or contradict earlier findings. Version history restores
the exact evidence set and analysis of previous completed revisions.

The **Unified timeline** places every source on one case clock, with source lanes,
uncertainty ranges, and clickable source timestamps. The **Working account** stores
a structured recollection: summary claims, observations, testimony, inferences,
questions, and conflicts. It is committed with a successful analysis, never
regenerated on page loads or uploads. Content-addressed entries reuse unchanged
text and references; superseded entries remain inspectable. The saved JSON is
available in the interface. This projection makes no extra model call.

Editing source details advances the evidence revision without modifying source
bytes or erasing the saved account. Earlier reconstructions retain their exact
annotations. Context edits invalidate synthesis, while extraction caches for the
unchanged media remain reusable. User notes are treated as unverified context,
never as instructions or independently observed facts.

Questions under **Missing evidence** have an **Answer question** action. Responses
retain their question, respondent, and revision; saving a response marks the case
for an update. Accepted findings cite the exact response version used, while
earlier reconstructions keep their original responses. See [case responses](docs/case-answers.md).

## Analysis modes

Copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY` to use live
analysis. `GEMINI_MODEL` selects the model. Environment files and original uploaded
media are gitignored. Never put credentials in frontend runtime configuration.

With no key, new uploads use explicitly labeled **simulated analysis** to exercise
the workflow. Mock findings describe workflow and do not claim to have inspected
the uploaded incident. `just demo-mock` forces this mode even when a key exists.
With a key, Analyze uses Gemini and reports a readable error if it fails. Errors
never silently substitute mock evidence. Previously completed analysis remains
saved on the case, and exact-content extraction caches can be reused on retry.

Original uploads and SQLite are stored under `data/`. Live analysis sends evidence
to Gemini; when configured, sampled images and extracted text also go to TypeSafe.
Per-file extraction and synthesis are cached by content, model, and prompt version;
uploading identical bytes again reuses analysis and remaps source references to the
new case. Cache hits do not call Gemini.

## Jev evidence checks

Set `TYPESAFE_API_KEY` server-side to enable Jev image and text judgments during
live analysis. The model is pinned to `jev-1.14.0`; every image/Box request sends
`TypeSafe-Danger-Zone-Images: true`. `REWIND_TYPESAFE_ENABLED=false` disables it.
The bounded sample count is `REWIND_TYPESAFE_MAX_FRAMES` (default 8 per video).
Up to four images share a request; cached frame judgments remain reusable.
A separate **Quick scan** appears while Gemini continues detailed reconstruction.
It contains provisional frame classifications and source-clock links, and never
replaces the accepted account or history until detailed analysis succeeds.


Jev classifies sampled images, labels extraction text, and checks summary claims
against their cited source intervals. **Evidence signals** shows saved probabilities
and source-time navigation. These signals remain separate from accepted claims and
working memory. They are cached by content, model and question versions, and older
reconstructions preserve their own results. Failures leave useful partial results
and do not fail detailed reconstruction. Simulated analysis makes no provider calls.

See [capabilities, examples and evaluation plan](docs/typesafe-images-research.md).
Accuracy and cost comparisons are tracked in GitHub issue #13; sampled negatives
must not be used to rule out events between frames.

For multiple videos, Jev checks whether they depict the same incident from different
cameras. Plausible uncertain pairs can receive a bounded detailed visual comparison.
The interface preserves both assessments and opens each original source. These
checks do not automatically synchronize clocks. See [video comparisons](docs/video-viewpoints.md).


## Commands

| Task | Command |
| --- | --- |
| Install locked dependencies | `just setup` |
| Start both servers | `just demo` |
| Force simulated analysis | `just demo-mock` |
| Regenerate JSON schema and TypeScript | `just types` |
| Backend tests, frontend tests, type checking, contract drift | `just check` |
| Build the production frontend | `just build` |
| Analyze demo files with Gemini and print source times | `just check-live` |
| Browser acceptance checks (isolated servers and database) | `just check-browser` |
| Require and test every prepared real incident clip | `just check-clips` |
| Prepare the fifteen reviewed local incident clips | `just prepare-clips` |
| Prepare real dashcam incident and partial clips | `just prepare-footage` |

`just check-live` is an explicit live check and fails if credentials or Gemini fail.
It can use an existing live cache. To require actual requests without deleting any
cache, run `uv run --project backend python -m rewind.analysis.check_live --root . --fresh`.

For browser checks, install Chromium once with
`cd e2e && bunx playwright install chromium` after installing the e2e dependencies.
Browser checks start their own frontend on port 3123 and API on port 8123, with
temporary SQLite and Nuxt build directories. They force simulated analysis and
do not populate or modify the user workspace on port 3000. The prepared real clips
are included automatically when their manifest exists; `just check-clips` requires
that dataset and fails if it is missing. Browser action tests make no Gemini calls.

The full-compilation test set is in `data/test-clips/`: fifteen numbered incident
videos, an upload guide, source-clock mappings, hashes, and review sheets. See
[reviewed selections and reproduction](demo/real-footage/test-set.md). Each clip
shows a different incident and should be uploaded as a separate case. Preparing
or testing the dataset does not import anything into the user database.

Real dashcam test data is prepared under `data/footage/`. The 25-second
`van-incident.mp4` and before/impact/after fragments preserve the original recording
and timestamp mappings in `manifest.json`. See
[provenance and attribution](demo/real-footage/metadata.md). These files remain
outside Git; their reproducible preparation script is committed. Follow-up
[eval issue #13](https://github.com/arniber21/echo/issues/13) compares partial clips
with the full incident against human annotations.

## Evidence semantics

- Video time zero anchors the merged case axis. Clicking an event seeks the source
  player to `source_start`, never to the estimated `case_best` placement.
- Audio statements use content alignment, explicit confidence, and uncertainty
  ranges. Testimony remains testimony.
- Photos use capture metadata when available. A timestamp without a shared clock
  cannot establish a precise position relative to the video. Unknown times remain
  open-ended and link to the events they support.
- Observations, inferences, and testimony are distinguished. No AI output is
  verified. Contradictions link to both conflicting sources; gaps describe what is
  not established. The application does not determine fault.
- The report route preserves these labels and includes every source file. Use
  browser Print → Save as PDF; there is no server-side PDF service.

See [SPEC.md](SPEC.md), [IMPLEMENTATION.md](IMPLEMENTATION.md), and
[docs/demo-script.md](docs/demo-script.md) for scope, boundaries, and rehearsal.

Contributor coordination: [CONTRIBUTING.md](CONTRIBUTING.md). Claim an issue before starting work.
