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

The home page opens a **synthetic, pre-analyzed demonstration**, including playable
media and a deliberate contradiction. It works without a Gemini key or network
access after dependencies have been installed. See [demo/README.md](demo/README.md)
for what each file depicts.

## Analysis modes

Copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY` to use live
analysis. `GEMINI_MODEL` selects the model. Environment files and original uploaded
media are gitignored. Never put credentials in frontend runtime configuration.

With no key, new uploads use explicitly labeled **simulated analysis** to exercise
the workflow. Mock findings describe workflow and do not claim to have inspected
the uploaded incident. `just demo-mock` forces this mode even when a key exists.
With a key, Analyze uses Gemini and reports a readable error if it fails. Errors
never silently substitute mock evidence. The pre-analyzed demonstration remains
available through the demo action.

Original uploads and SQLite are stored under `data/`. Gemini is the sole external
recipient of evidence during live analysis. Use synthetic or consented media.
Per-file extraction and synthesis are cached by content, model, and prompt version;
uploading identical bytes again reuses analysis and remaps source references to the
new case. Cache hits do not call Gemini.

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
| Browser acceptance checks (servers running) | `just check-browser` |
| Prepare real dashcam incident and partial clips | `just prepare-footage` |

`just check-live` is an explicit live check and fails if credentials or Gemini fail.
It can use an existing live cache. To require actual requests without deleting any
cache, run `uv run --project backend python -m rewind.analysis.check_live --root . --fresh`.

For browser checks, install Chromium once with
`cd e2e && bunx playwright install chromium` after installing the e2e dependencies.
Use `just demo-mock` for the automated rehearsal so it is deterministic and incurs
no API usage.

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
