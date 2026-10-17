"""Extraction, evidence-preserving synthesis, and identity-independent disk caching."""

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from pathlib import Path

from rewind.intelligence.models import EvidenceIntelligence
from rewind.models import Analysis, Case, MediaFile, validate_analysis

from .cache import JsonCache, cache_key
from .content_alignment import find_content_alignments
from .mock import mock_analysis
from .prompts import (
    PROMPT_VERSION,
    SYNTHESIS_PROMPT,
    SYNTHESIS_PROMPT_VERSION,
    extraction_prompt,
)
from .provider import GeminiProvider
from .types import AnalysisSettings, Extraction
from .validation import finalize_synthesis, validate_extraction, validate_synthesis

Progress = Callable[[str, int], Awaitable[None]]
IntelligenceSink = Callable[[EvidenceIntelligence], Awaitable[None]]
logger = logging.getLogger(__name__)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remap(result: Analysis, ids: Mapping[str, str]) -> Analysis:
    payload = result.model_dump(mode="json")
    if payload["clock_source_id"] is not None:
        payload["clock_source_id"] = ids[payload["clock_source_id"]]
    for event in payload["events"]:
        event["source_id"] = ids[event["source_id"]]
    for item in [
        *payload["summary"],
        *payload["missing_evidence"],
        *payload["contradictions"],
    ]:
        for ref in item["source_refs"]:
            ref["source_id"] = ids[ref["source_id"]]
    return Analysis.model_validate(payload)


async def analyze(
    case: Case,
    media_paths: Mapping[str, Path],
    progress: Progress,
    *,
    settings: AnalysisSettings | None = None,
    intelligence_sink: IntelligenceSink | None = None,
) -> Analysis:
    """Analyze all case files. A live error is never silently replaced by mock data."""
    settings = settings or AnalysisSettings()
    if settings.mode == "mock" or (settings.mode == "auto" and not settings.api_key):
        await progress("synthesizing", 90)
        return validate_analysis(mock_analysis(case), case.media_files, case.answers)
    if not settings.api_key:
        raise ValueError("Live analysis requires GEMINI_API_KEY")
    if not case.media_files:
        raise ValueError("Analysis requires at least one media source")

    # Sort by role and actual content; database-generated ids never enter cache identity.
    hashed = [
        (source, await asyncio.to_thread(_digest, media_paths[source.source_id]))
        for source in case.media_files
    ]
    hashed.sort(
        key=lambda pair: (pair[0].source_type.value, pair[1], pair[0].source_id)
    )
    canonical: list[MediaFile] = []
    paths: dict[str, Path] = {}
    real_ids: dict[str, str] = {}
    for index, (source, digest) in enumerate(hashed):
        source_id = f"source-{index}"
        canonical.append(
            source.model_copy(update={"source_id": source_id, "sha256": digest})
        )
        paths[source_id] = media_paths[source.source_id]
        real_ids[source_id] = source.source_id
    # Primary video is explicitly deterministic, independent of database ids or upload order.
    canonical.sort(
        key=lambda source: (
            source.source_type.value != "video",
            -(source.duration_seconds or 0)
            if source.source_type.value == "video"
            else 0,
            source.sha256,
            source.source_id,
        )
    )
    cache = JsonCache(settings.cache_dir)
    extractions: dict[str, Extraction] = {}
    provider: GeminiProvider | None = None
    intelligence_service = None
    intelligence_report: EvidenceIntelligence | None = None

    async def publish_intelligence(report: EvidenceIntelligence) -> None:
        if intelligence_sink is not None:
            mapped = report.model_copy(
                update={
                    "sources": [
                        source.model_copy(
                            update={"source_id": real_ids[source.source_id]}
                        )
                        for source in report.sources
                    ],
                    "video_relationships": [
                        relationship.model_copy(
                            update={
                                "source_a": real_ids[relationship.source_a],
                                "source_b": real_ids[relationship.source_b],
                            }
                        )
                        for relationship in report.video_relationships
                    ],
                }
            )
            await intelligence_sink(mapped)

    def get_provider() -> GeminiProvider:
        nonlocal provider
        if provider is None:
            provider = GeminiProvider(settings)
        return provider

    try:
        if settings.typesafe_api_key:
            intelligence_report = EvidenceIntelligence(
                model=settings.typesafe_model,
                version="unavailable",
                status="unavailable",
            )
            await progress("classifying_evidence", 8)
            try:
                from rewind.intelligence.service import JevIntelligence

                intelligence_service = JevIntelligence(
                    api_key=settings.typesafe_api_key,
                    model=settings.typesafe_model,
                    cache_dir=settings.cache_dir,
                    max_frames=settings.typesafe_max_frames,
                )
                intelligence_report = await intelligence_service.scan_sources(
                    canonical, paths
                )
            except Exception:  # noqa: BLE001 - optional classifiers cannot fail reconstruction
                logger.warning("Jev visual classification unavailable")
                intelligence_report.diagnostics.append(
                    "visual_classification_unavailable"
                )
            await publish_intelligence(intelligence_report)
        for index, media in enumerate(canonical):
            stage = {
                "video": "analyzing_video",
                "audio": "analyzing_audio",
                "photo": "analyzing_photos",
            }[media.source_type.value]
            await progress(stage, 10 + int(index / len(canonical) * 60))
            key = cache_key(
                {
                    "version": PROMPT_VERSION,
                    "model": settings.model,
                    "task": "extract",
                    "role": media.source_type.value,
                    "hash": media.sha256,
                    "duration": media.duration_seconds,
                }
            )
            extracted = await asyncio.to_thread(cache.read, key, Extraction)
            if extracted is not None:
                try:
                    validate_extraction(extracted, media)
                except ValueError:
                    extracted = None
            if extracted is None:
                extracted = await get_provider().generate(
                    extraction_prompt(media.source_type.value, media.duration_seconds),
                    Extraction,
                    path=paths[media.source_id],
                    mime_type=media.mime_type,
                    validate=lambda result, source=media: validate_extraction(
                        result, source
                    ),
                )
                await asyncio.to_thread(cache.write, key, extracted)
            extractions[media.source_id] = extracted
        records = []
        for source in canonical:
            events = []
            for index, event in enumerate(extractions[source.source_id].events):
                events.append(
                    {
                        **event.model_dump(mode="json"),
                        "event_id": f"event-{source.source_id}-{index}",
                        "source_id": source.source_id,
                        "source_type": source.source_type.value,
                    }
                )
            records.append(
                {
                    "source_id": source.source_id,
                    "source_type": source.source_type.value,
                    "sha256": source.sha256,
                    "duration_seconds": source.duration_seconds,
                    "captured_at": source.captured_at.isoformat()
                    if source.captured_at
                    else None,
                    "source_metadata": source.metadata.model_dump(mode="json"),
                    "events": events,
                    "limitations": extractions[source.source_id].limitations,
                }
            )
        # Clock alignment is measured against actual media bytes, not inferred
        # from filenames, source timestamps, or classifier incident identity.
        await progress("matching_views", 72)
        alignments = await find_content_alignments(canonical, paths, cache)
        for record in records:
            measured = alignments.get(record["source_id"])
            record["measured_clock_alignment"] = asdict(measured) if measured else None
        if (
            intelligence_service is not None
            and intelligence_report is not None
            and sum(source.source_type.value == "video" for source in canonical) > 1
        ):
            await progress("matching_views", 75)
            try:
                intelligence_report = await intelligence_service.compare_views(
                    canonical, paths, records, intelligence_report
                )
            except Exception:  # noqa: BLE001 - optional comparisons cannot fail reconstruction
                logger.warning("Jev video comparison unavailable")
                intelligence_report = intelligence_report.model_copy(
                    update={
                        "diagnostics": [
                            *intelligence_report.diagnostics,
                            "video_comparison_unavailable",
                        ],
                        "status": "partial"
                        if intelligence_report.sources
                        else "unavailable",
                    }
                )
            if any(
                pair.relationship == "uncertain"
                for pair in intelligence_report.video_relationships
            ):
                from .view_review import review_uncertain_views

                intelligence_report = await review_uncertain_views(
                    get_provider(),
                    canonical,
                    paths,
                    records,
                    intelligence_report,
                    cache,
                    settings.model,
                )
                intelligence_report = (
                    await intelligence_service.confirm_view_event_matches(
                        records, intelligence_report
                    )
                )
            await publish_intelligence(intelligence_report)
        records[0]["video_relationships"] = (
            [
                relationship.model_dump(mode="json")
                for relationship in intelligence_report.video_relationships
            ]
            if intelligence_report
            else []
        )
        await progress("synthesizing", 80)
        # Answers influence synthesis only; media extraction remains immutable/cacheable.
        records[0]["case_answers"] = [
            answer.model_dump(mode="json") for answer in case.answers
        ]
        key = cache_key(
            {
                "version": SYNTHESIS_PROMPT_VERSION,
                "model": settings.model,
                "task": "synthesize",
                "records": records,
            }
        )
        result = await asyncio.to_thread(cache.read, key, Analysis)
        if result is not None:
            try:
                validate_synthesis(
                    result, canonical, extractions, case.answers, alignments
                )
            except ValueError:
                result = None
        if result is None:
            result = await get_provider().generate(
                SYNTHESIS_PROMPT + json.dumps(records),
                Analysis,
                validate=lambda output: finalize_synthesis(
                    output, canonical, extractions, case.answers, alignments
                ),
            )
            result = result.model_copy(
                update={
                    "mode": "live",
                    "notice": "AI-generated analysis. All findings are unverified.",
                }
            )
            await asyncio.to_thread(cache.write, key, result)
        else:
            result = result.model_copy(
                update={
                    "mode": "cached",
                    "notice": "Cached AI analysis for these exact source files. All findings remain unverified.",
                }
            )
        if intelligence_service is not None and intelligence_report is not None:
            await progress("checking_claims", 95)
            try:
                intelligence_report = await intelligence_service.assess_analysis(
                    result, records, intelligence_report
                )
            except Exception:  # noqa: BLE001 - preserve the completed reconstruction
                logger.warning("Jev text assessment unavailable")
                intelligence_report = intelligence_report.model_copy(
                    update={
                        "status": "partial"
                        if intelligence_report.sources
                        else "unavailable",
                        "diagnostics": [
                            *intelligence_report.diagnostics,
                            "text_assessment_unavailable",
                        ],
                    }
                )
            await publish_intelligence(intelligence_report)
        return validate_analysis(
            _remap(result, real_ids), case.media_files, case.answers
        )
    finally:
        if provider is not None:
            await provider.close()
        if intelligence_service is not None:
            try:
                await intelligence_service.close()
            except Exception:  # noqa: BLE001 - classifier cleanup cannot hide valid output
                logger.warning("Jev client cleanup unavailable")
