"""Safe offline flow: simulated placeholders never assert an uploaded incident."""

from rewind.models import Analysis, Case, Claim, Event, Finding, SourceRef, SourceType


def mock_analysis(case: Case) -> Analysis:
    events = []
    for index, media in enumerate(case.media_files):
        is_photo = media.source_type == SourceType.PHOTO
        events.append(
            Event(
                event_id=f"mock-event-{index}",
                source_id=media.source_id,
                source_type=media.source_type,
                title=f"Simulated {media.source_type.value} marker",
                description="Offline placeholder only. This file has not been inspected and no incident fact is established.",
                source_start=None if is_photo else 0,
                source_end=None if is_photo else 0,
                case_min=0,
                case_best=0,
                case_max=None
                if is_photo or media.source_type == SourceType.AUDIO
                else 0.5,
                alignment_basis="Simulated placement; media content has not been analyzed",
                alignment_confidence=0,
                confidence=0,
                evidence_type="inference",
            )
        )
    refs = [SourceRef(source_id=media.source_id) for media in case.media_files]
    return Analysis(
        events=events,
        summary=[
            Claim(
                text="Simulated analysis only: uploaded files are available to inspect, but their contents have not been analyzed.",
                source_refs=refs,
            )
        ]
        if refs
        else [],
        missing_evidence=[
            Finding(
                id="mock-analysis-required",
                title="Evidence analysis is required",
                description="Configure Gemini and run live analysis, or review the sources manually.",
                source_refs=refs,
            )
        ],
        contradictions=[],
        mode="mock",
        notice="SIMULATED: no Gemini request was made. Markers are placeholders, not findings about your files.",
    )
