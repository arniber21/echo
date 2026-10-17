"""Explicit opt-in live smoke test. API errors exit nonzero, never fall back."""

import argparse
import asyncio
import json
import os
import subprocess
from pathlib import Path

from dotenv import dotenv_values

from rewind.models import Case

from .pipeline import analyze
from .types import AnalysisSettings


async def check(root: Path, fresh: bool) -> None:
    environment = dotenv_values(root / "backend/.env")
    key = os.environ.get("GEMINI_API_KEY") or environment.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required for the explicit live check")
    case = Case.model_validate_json((root / "shared/sample_case.json").read_text())
    paths = {media.source_id: root / "demo/media" / media.filename for media in case.media_files}
    for source in case.media_files:
        if source.source_type.value != "photo":
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(paths[source.source_id])],
                check=True, capture_output=True, text=True, timeout=30,
            )
            source.duration_seconds = float(json.loads(probe.stdout)["format"]["duration"])

    async def progress(stage: str, percent: int) -> None:
        print(f"{percent:3d}% {stage}", flush=True)

    cache_dir = root / "data/cache"
    if fresh:
        # A separate cache namespace guarantees API calls without deleting persisted results.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(prefix="rewind-live-") as directory:
            result = await analyze(case, paths, progress, settings=AnalysisSettings(
                api_key=key, model=os.environ.get("GEMINI_MODEL") or environment.get("GEMINI_MODEL") or "gemini-2.5-flash",
                mode="live", cache_dir=Path(directory),
            ))
    else:
        result = await analyze(case, paths, progress, settings=AnalysisSettings(
            api_key=key, model=os.environ.get("GEMINI_MODEL") or environment.get("GEMINI_MODEL") or "gemini-2.5-flash",
            mode="live", cache_dir=cache_dir,
        ))
    print(f"Analysis mode: {result.mode}; {len(result.events)} events; {len(result.contradictions)} contradictions")
    for event in result.events:
        print(f"{event.source_id}: source={event.source_start}..{event.source_end}; case={event.case_min}..{event.case_best}..{event.case_max}; {event.evidence_type}; {event.title}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--fresh", action="store_true", help="Use an isolated empty cache to require live requests")
    options = parser.parse_args()
    asyncio.run(check(options.root.resolve(), options.fresh))


if __name__ == "__main__":
    main()
