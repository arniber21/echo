"""Cross-source integrity rules beyond the public JSON schema."""

from collections.abc import Mapping

from rewind.models import Analysis, MediaFile, SourceType, validate_analysis

from .types import Extraction


def validate_extraction(result: Extraction, media: MediaFile) -> None:
    for event in result.events:
        if media.source_type == SourceType.PHOTO:
            if event.source_start is not None or event.source_end is not None:
                raise ValueError("Photos do not have seek times")
        else:
            if event.source_start is None or event.source_end is None:
                raise ValueError("Timed extraction requires source times")
            if media.duration_seconds is not None and event.source_end > media.duration_seconds + 0.1:
                raise ValueError("Extraction exceeds source duration")


def validate_synthesis(
    result: Analysis, media: list[MediaFile], extractions: Mapping[str, Extraction]
) -> None:
    validate_analysis(result, media)
    expected = {
        f"event-{source_id}-{index}": (source_id, event)
        for source_id, extraction in extractions.items()
        for index, event in enumerate(extraction.events)
    }
    if {event.event_id for event in result.events} != set(expected):
        raise ValueError("Synthesis must retain all and only extracted events")
    source_map = {source.source_id: source for source in media}
    anchor = next((source for source in media if source.source_type == SourceType.VIDEO), None)
    for event in result.events:
        source_id, extracted = expected[event.event_id]
        if (event.source_id, event.source_start, event.source_end, event.evidence_type) != (
            source_id, extracted.source_start, extracted.source_end, extracted.evidence_type
        ):
            raise ValueError("Synthesis changed source evidence or seek timestamps")
        if event.event_id in event.supports:
            raise ValueError("An event cannot support itself")
        if event.case_best < 0 or (event.case_min is not None and event.case_min < 0):
            raise ValueError("Case placement must be nonnegative")
        if anchor and source_id == anchor.source_id:
            if event.case_best != event.source_start:
                raise ValueError("Primary video must anchor the case clock")
            if event.case_min is None or event.case_max is None:
                raise ValueError("Primary video needs a finite uncertainty window")
            if event.case_best - event.case_min > 0.51 or event.case_max - event.case_best > 0.51:
                raise ValueError("Primary video uncertainty must remain tight")
        source = source_map[source_id]
        if source.source_type == SourceType.PHOTO:
            if not (source.captured_at and anchor and anchor.captured_at) and event.case_max is not None:
                raise ValueError("Photos without relative capture metadata need an open end")
        if source.source_type == SourceType.AUDIO and event.alignment_confidence <= 0.3:
            if event.case_min is not None and event.case_max is not None and event.case_max - event.case_min < 10:
                raise ValueError("Unmatched audio must retain a wide uncertainty window")
    for item in [*result.summary, *result.missing_evidence, *result.contradictions]:
        for ref in item.source_refs:
            if source_map[ref.source_id].source_type == SourceType.PHOTO:
                if ref.source_start is not None or ref.source_end is not None:
                    raise ValueError("Photo references cannot contain seek times")
