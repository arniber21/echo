"""Persisted classifier observations, separate from accepted reconstruction claims."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Probability = Annotated[float, Field(ge=0, le=1)]


class IntelligenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BoxEdges(IntelligenceModel):
    top: Probability
    bottom: Probability
    left: Probability
    right: Probability

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.top >= self.bottom or self.left >= self.right:
            raise ValueError("Box edges must enclose a positive area")
        return self


class FrameAssessment(IntelligenceModel):
    source_time: float | None = Field(default=None, ge=0)
    signals: dict[str, Probability]
    vehicle_box: BoxEdges | None = None
    box_confidence: Probability | None = None
    image_sha256: str = ""
    prepared_width: int = Field(default=0, ge=0)
    prepared_height: int = Field(default=0, ge=0)


class SourceIntelligence(IntelligenceModel):
    source_id: str
    frames: list[FrameAssessment] = Field(default_factory=list)
    labels: dict[str, Probability] = Field(default_factory=dict)


class ClaimAssessment(IntelligenceModel):
    claim_index: int = Field(ge=0)
    supported_probability: Probability
    overclaim_probability: Probability


class ViewEventMatch(IntelligenceModel):
    event_a: str
    event_b: str
    probability: Probability


class DetailedViewReview(IntelligenceModel):
    relationship: Literal[
        "same_incident_different_view",
        "same_footage",
        "different_incident",
        "uncertain",
    ]
    confidence: Probability
    basis: str = Field(min_length=1, max_length=2000)
    matches: list[ViewEventMatch] = Field(default_factory=list, max_length=24)
    model: str


class VideoRelationship(IntelligenceModel):
    source_a: str
    source_b: str
    relationship: Literal[
        "same_incident_different_view",
        "same_footage",
        "different_incident",
        "uncertain",
    ]
    confidence: Probability
    same_incident_probability: Probability
    different_view_probability: Probability
    basis: str
    matches: list[ViewEventMatch] = Field(default_factory=list)
    detailed_review: DetailedViewReview | None = None


class EvidenceIntelligence(IntelligenceModel):
    model: str
    version: str
    status: Literal["complete", "partial", "unavailable"]
    sources: list[SourceIntelligence] = Field(default_factory=list)
    claims: list[ClaimAssessment] = Field(default_factory=list)
    video_relationships: list[VideoRelationship] = Field(default_factory=list)
    input_tokens: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    diagnostics: list[str] = Field(default_factory=list, max_length=100)
