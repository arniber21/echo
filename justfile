set dotenv-load := false

# List available tasks. Run with `devbox run -- just <task>` or in `devbox shell`.
default:
    @just --list

# Install application dependencies using the committed lockfiles.
setup:
    uv sync --project backend --frozen
    cd frontend && bun install --frozen-lockfile

# Start both local servers; Ctrl-C stops both.
demo:
    python3 scripts/dev.py

# Start explicitly simulated analysis; never contacts Gemini.
demo-mock:
    REWIND_ANALYSIS_MODE=mock python3 scripts/dev.py

# Regenerate the shared JSON schema and TypeScript from Pydantic.
types:
    uv run --project backend python backend/scripts/generate_types.py

# Run integrity checks, backend tests, frontend tests, and TypeScript checking.
check:
    uv run --project backend pytest backend/tests
    cd frontend && bun run test
    cd frontend && bun run typecheck
    cd frontend && bunx prettier --check app tests nuxt.config.ts
    just types
    git diff --exit-code -- shared/schema.json frontend/app/types/generated.ts

# Build the frontend production bundle.
build:
    cd frontend && bun run build

# Exercise Gemini against the synthetic demo; requires backend/.env key.
check-live:
    uv run --project backend python -m rewind.analysis.check_live --root .

# Run browser acceptance checks on isolated temporary servers and storage.
check-browser:
    cd e2e && bun install --frozen-lockfile
    cd e2e && bunx tsc --noEmit
    cd e2e && bunx playwright test

# Require the real clip dataset and exercise uploads, annotations, playback, and analysis.
check-clips:
    cd e2e && bun install --frozen-lockfile
    cd e2e && REWIND_REQUIRE_REAL_CLIPS=1 bunx playwright test --grep @real-clips

# Download and splice attributed real dashcam data under ignored data/footage/.
prepare-footage:
    python3 scripts/prepare_dashcam.py

# Reproduce the fifteen reviewed clips from the local compilation without importing cases.
prepare-clips:
    python3 scripts/prepare_local_test_set.py
