"""Provider-neutral extraction contract and pipeline configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass(frozen=True)
class AnalysisSettings:
    api_key: str | None = None
    model: str = "gemini-3.8-flash"
    mode: Literal["auto", "mock", "live"] = "auto"
    cache_dir: Path = Path("data/cache")
    upload_timeout_seconds: float = 180
    request_timeout_seconds: float = 180


class ExtractedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    title: str
    description: str
    source_start: float | None
    source_end: float | None
    evidence_type: Literal["observation", "inference", "testimony"]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered_times(self) -> "ExtractedEvent":
        if (self.source_start is None) != (self.source_end is None):
            raise ValueError("source times must both be present or absent")
        if (
            self.source_start is not None
            and self.source_end is not None
            and not 0 <= self.source_start <= self.source_end
        ):
            raise ValueError("source times must be nonnegative and ordered")
        return self


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    events: list[ExtractedEvent]
    limitations: list[str]
