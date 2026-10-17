"""Deterministic, provisional frame labels for the first usable case view."""

from datetime import UTC, datetime

from rewind.models import (
    Analysis,
    Case,
    Claim,
    Event,
    ReconstructionPreview,
    SourceRef,
    SourceType,
    validate_analysis,
)

from .models import EvidenceIntelligence

# Display candidates only. These thresholds do not decide whether footage is
# relevant or whether an incident occurred; full originals remain available.
CANDIDATES = (
    ("vehicle_contact_visible", "Possible vehicle contact"),
    ("damage_visible", "Possible visible damage"),
    ("vehicle_visible", "Vehicle in sampled image"),
    ("road_visible", "Road in sampled image"),
)


def classification_preview(
    case: Case, report: EvidenceIntelligence
) -> ReconstructionPreview | None:
    sources = {source.source_id: source for source in case.media_files}
    sampled = [
        entry for entry in report.sources if entry.frames and entry.source_id in sources
    ]
    if not sampled:
        return None
    videos = [
        source for source in case.media_files if source.source_type == SourceType.VIDEO
    ]
    anchor = (
        min(videos, key=lambda source: (source.sha256, source.source_id))
        if videos
        else None
    )
    events = []
    for entry in sampled:
        source = sources[entry.source_id]
        for index, frame in enumerate(entry.frames):
            candidate = next(
                (
                    (key, title)
                    for key, title in CANDIDATES
                    if frame.signals.get(key, 0) >= 0.8
                ),
                None,
            )
            if candidate is None:
                continue
            key, title = candidate
            timestamp = (
                frame.source_time if source.source_type == SourceType.VIDEO else None
            )
            if source.source_type == SourceType.VIDEO and timestamp is None:
                continue
            primary = anchor is not None and source.source_id == anchor.source_id
            best = timestamp if primary else 0
            events.append(
                Event(
                    event_id=f"preview-{source.source_id}-{index}",
                    source_id=source.source_id,
                    source_type=source.source_type,
                    source_start=timestamp,
                    source_end=timestamp,
                    case_min=max(0, best - 0.5) if primary else 0,
                    case_best=best,
                    case_max=best + 0.5 if primary else None,
                    title=title,
                    description=(
                        f"Jev classification probability: {frame.signals[key]:.2f}. "
                        "This sampled image does not establish motion or what occurred between samples."
                    ),
                    evidence_type="inference",
                    confidence=frame.signals[key],
                    alignment_basis="Primary video source clock"
                    if primary
                    else "Relative timing unknown",
                    alignment_confidence=1 if primary else 0,
                )
            )
    analysis = Analysis(
        events=events,
        summary=[
            Claim(
                text=(
                    f"Classified {sum(len(entry.frames) for entry in sampled)} sampled images "
                    f"from {len(sampled)} sources. Unsampled intervals and cross-source timing remain unestablished."
                ),
                source_refs=[SourceRef(source_id=entry.source_id) for entry in sampled],
            )
        ],
        mode="live",
        notice="Quick classification scan; detailed reconstruction pending.",
    )
    return ReconstructionPreview(
        evidence_revision=case.evidence_revision,
        created_at=datetime.now(UTC),
        analysis=validate_analysis(analysis, case.media_files),
        intelligence=report,
    )
