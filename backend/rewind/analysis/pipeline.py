"""Extraction, evidence-preserving synthesis, and identity-independent disk caching."""

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path

from rewind.models import Analysis, Case, MediaFile, validate_analysis

from .cache import JsonCache, cache_key
from .mock import mock_analysis
from .prompts import PROMPT_VERSION, SYNTHESIS_PROMPT, extraction_prompt
from .provider import GeminiProvider
from .types import AnalysisSettings, Extraction
from .validation import validate_extraction, validate_synthesis

Progress = Callable[[str, int], Awaitable[None]]


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remap(result: Analysis, ids: Mapping[str, str]) -> Analysis:
    payload = result.model_dump(mode="json")
    for event in payload["events"]:
        event["source_id"] = ids[event["source_id"]]
    for item in [*payload["summary"], *payload["missing_evidence"], *payload["contradictions"]]:
        for ref in item["source_refs"]:
            ref["source_id"] = ids[ref["source_id"]]
    return Analysis.model_validate(payload)


async def analyze(
    case: Case,
    media_paths: Mapping[str, Path],
    progress: Progress,
    *,
    settings: AnalysisSettings | None = None,
) -> Analysis:
    """Analyze all case files. A live error is never silently replaced by mock data."""
    settings = settings or AnalysisSettings()
    if settings.mode == "mock" or (settings.mode == "auto" and not settings.api_key):
        await progress("synthesizing", 90)
        return validate_analysis(mock_analysis(case), case.media_files)
    if not settings.api_key:
        raise ValueError("Live analysis requires GEMINI_API_KEY")
    if not case.media_files:
        raise ValueError("Analysis requires at least one media source")

    # Sort by role and actual content; database-generated ids never enter cache identity.
    hashed = [(source, await asyncio.to_thread(_digest, media_paths[source.source_id])) for source in case.media_files]
    hashed.sort(key=lambda pair: (pair[0].source_type.value, pair[1], pair[0].source_id))
    canonical: list[MediaFile] = []
    paths: dict[str, Path] = {}
    real_ids: dict[str, str] = {}
    for index, (source, digest) in enumerate(hashed):
        source_id = f"source-{index}"
        canonical.append(source.model_copy(update={"source_id": source_id, "sha256": digest}))
        paths[source_id] = media_paths[source.source_id]
        real_ids[source_id] = source.source_id
    # Primary video is explicitly deterministic, independent of database ids or upload order.
    canonical.sort(key=lambda source: (source.source_type.value != "video", source.source_id))
    cache = JsonCache(settings.cache_dir)
    extractions: dict[str, Extraction] = {}
    provider: GeminiProvider | None = None

    def get_provider() -> GeminiProvider:
        nonlocal provider
        if provider is None:
            provider = GeminiProvider(settings)
        return provider

    try:
        for index, media in enumerate(canonical):
            stage = {"video": "analyzing_video", "audio": "analyzing_audio", "photo": "analyzing_photos"}[media.source_type.value]
            await progress(stage, 10 + int(index / len(canonical) * 60))
            key = cache_key({"version": PROMPT_VERSION, "model": settings.model, "task": "extract", "role": media.source_type.value, "hash": media.sha256, "duration": media.duration_seconds})
            extracted = await asyncio.to_thread(cache.read, key, Extraction)
            if extracted is not None:
                try:
                    validate_extraction(extracted, media)
                except ValueError:
                    extracted = None
            if extracted is None:
                extracted = await get_provider().generate(
                    extraction_prompt(media.source_type.value, media.duration_seconds), Extraction,
                    path=paths[media.source_id], mime_type=media.mime_type,
                    validate=lambda result, source=media: validate_extraction(result, source),
                )
                await asyncio.to_thread(cache.write, key, extracted)
            extractions[media.source_id] = extracted
        await progress("synthesizing", 80)
        records = []
        for source in canonical:
            events = []
            for index, event in enumerate(extractions[source.source_id].events):
                events.append({**event.model_dump(mode="json"), "event_id": f"event-{source.source_id}-{index}", "source_id": source.source_id, "source_type": source.source_type.value})
            records.append({
                "source_id": source.source_id, "source_type": source.source_type.value,
                "sha256": source.sha256, "duration_seconds": source.duration_seconds,
                "captured_at": source.captured_at.isoformat() if source.captured_at else None,
                "events": events, "limitations": extractions[source.source_id].limitations,
            })
        key = cache_key({"version": PROMPT_VERSION, "model": settings.model, "task": "synthesize", "records": records})
        result = await asyncio.to_thread(cache.read, key, Analysis)
        if result is not None:
            try:
                validate_synthesis(result, canonical, extractions)
            except ValueError:
                result = None
        if result is None:
            result = await get_provider().generate(
                SYNTHESIS_PROMPT + json.dumps(records), Analysis,
                validate=lambda output: validate_synthesis(output, canonical, extractions),
            )
            result = result.model_copy(update={"mode": "live", "notice": "AI-generated analysis. All findings are unverified."})
            await asyncio.to_thread(cache.write, key, result)
        else:
            result = result.model_copy(update={"mode": "cached", "notice": "Cached AI analysis for these exact source files. All findings remain unverified."})
        return validate_analysis(_remap(result, real_ids), case.media_files)
    finally:
        if provider is not None:
            await provider.close()
