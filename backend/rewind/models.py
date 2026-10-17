"""Canonical validated API contracts; generated clients derive from these models."""

from datetime import datetime
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SourceType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    PHOTO = "photo"


class SourceRef(Contract):
    source_id: str = Field(min_length=1, max_length=100)
    source_start: float | None = Field(default=None, ge=0)
    source_end: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if (
            self.source_end is not None
            and self.source_start is not None
            and self.source_end < self.source_start
        ):
            raise ValueError("source_end must be at or after source_start")
        return self


class Event(SourceRef):
    event_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=12000)
    source_type: SourceType
    case_min: float | None = None
    case_best: float
    case_max: float | None = None
    alignment_basis: str = Field(min_length=1, max_length=4000)
    alignment_confidence: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    verification_status: Literal["unverified"] = "unverified"
    evidence_type: Literal["observation", "inference", "testimony"]
    supports: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def placement(self) -> Self:
        if self.case_min is not None and self.case_min > self.case_best:
            raise ValueError("case_min must not exceed case_best")
        if self.case_max is not None and self.case_max < self.case_best:
            raise ValueError("case_max must not precede case_best")
        if self.source_type != SourceType.PHOTO and (
            self.source_start is None or self.source_end is None
        ):
            raise ValueError("Timed media events require source_start and source_end")
        if self.source_type == SourceType.PHOTO and (
            self.source_start is not None or self.source_end is not None
        ):
            raise ValueError("Photos must not have source timestamps")
        if self.event_id in self.supports:
            raise ValueError("An event cannot support itself")
        return self


class Claim(Contract):
    text: str = Field(min_length=1, max_length=8000)
    source_refs: list[SourceRef] = Field(min_length=1)


class Finding(Contract):
    id: str
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=12000)
    source_refs: list[SourceRef] = Field(default_factory=list)


class Analysis(Contract):
    events: list[Event]
    summary: list[Claim]
    missing_evidence: list[Finding] = Field(default_factory=list)
    contradictions: list[Finding] = Field(default_factory=list)
    mode: Literal["demo", "mock", "live", "cached"] = "live"
    notice: str | None = None


class MediaFile(Contract):
    source_id: str = Field(min_length=1, max_length=100)
    filename: str
    source_type: SourceType
    mime_type: str
    url: str
    sha256: str
    size_bytes: int = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    captured_at: datetime | None = None


class AnalysisRevision(Contract):
    """A previous completed reconstruction and its exact evidence set."""

    revision: int = Field(ge=1)
    created_at: datetime
    media_source_ids: list[str]
    analysis: Analysis


class Case(Contract):
    case_id: str
    title: str = Field(min_length=1, max_length=240)
    created_at: datetime
    media_files: list[MediaFile]
    analysis: Analysis | None = None
    evidence_revision: int = Field(default=1, ge=1)
    analyzed_revision: int | None = Field(default=None, ge=1)
    analyzed_at: datetime | None = None
    analyzed_source_ids: list[str] = Field(default_factory=list)
    analysis_history: list[AnalysisRevision] = Field(default_factory=list)


class Job(Contract):
    job_id: str
    case_id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: Literal[
        "uploading",
        "analyzing_video",
        "analyzing_audio",
        "analyzing_photos",
        "synthesizing",
        "completed",
        "failed",
    ]
    progress: int = Field(ge=0, le=100)
    error: str | None = None


def validate_analysis(analysis: Analysis, media: list[MediaFile]) -> Analysis:
    """Reject orphaned references and timestamps beyond the source duration."""
    analysis = Analysis.model_validate(analysis.model_dump())
    sources = {item.source_id: item for item in media}
    if len(sources) != len(media):
        raise ValueError("Media source IDs must be unique")
    videos = [item for item in media if item.source_type == SourceType.VIDEO]
    # File content selects the primary clock, independent of multipart order.
    primary_video = (
        min(videos, key=lambda item: (item.sha256, item.source_id)) if videos else None
    )
    event_ids = {event.event_id for event in analysis.events}
    if len(event_ids) != len(analysis.events):
        raise ValueError("Event IDs must be unique")
    refs = [*analysis.events]
    for claim in analysis.summary:
        refs.extend(claim.source_refs)
    for finding in [*analysis.missing_evidence, *analysis.contradictions]:
        refs.extend(finding.source_refs)
    for ref in refs:
        source = sources.get(ref.source_id)
        if source is None:
            raise ValueError(f"Unknown source reference: {ref.source_id}")
        if source.source_type == SourceType.PHOTO and (
            ref.source_start is not None or ref.source_end is not None
        ):
            raise ValueError("Photo references must not include source timestamps")
        if source.duration_seconds is not None:
            for value in (ref.source_start, ref.source_end):
                if value is not None and value > source.duration_seconds + 0.1:
                    raise ValueError("Source timestamp exceeds media duration")
    for event in analysis.events:
        if event.source_type == SourceType.VIDEO:
            if primary_video and event.source_id == primary_video.source_id:
                if abs(event.case_best - event.source_start) > 0.001:
                    raise ValueError(
                        "Primary video case placement must equal its source clock"
                    )
                if (
                    event.case_min is None
                    or event.case_max is None
                    or event.case_best - event.case_min > 0.501
                    or event.case_max - event.case_best > 0.501
                ):
                    raise ValueError("Primary video events need tight placement ranges")
            elif any(
                value is not None and value < 0
                for value in (event.case_min, event.case_best, event.case_max)
            ):
                raise ValueError("Secondary video placement ranges must be nonnegative")
        if sources[event.source_id].source_type != event.source_type:
            raise ValueError("Event source type does not match media")
        if not set(event.supports) <= event_ids:
            raise ValueError("Unknown supported event reference")
    for contradiction in analysis.contradictions:
        if len({ref.source_id for ref in contradiction.source_refs}) < 2:
            raise ValueError("Contradictions must reference both conflicting sources")
    return analysis


class AnalyzeRequest(Contract):
    mode: Literal["auto", "mock", "live"] = "auto"
