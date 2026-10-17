"""Bounded job diagnostics that never expose provider payloads or source content."""

from dataclasses import dataclass

import httpx
from google.genai.errors import APIError

from .provider import InvalidModelOutput, _validation_feedback


@dataclass(frozen=True)
class AnalysisFailure:
    code: str
    message: str
    validation: str | None = None


def classify_failure(error: Exception) -> AnalysisFailure:
    if isinstance(error, InvalidModelOutput):
        # Provider errors currently retain sanitized validation text in this prefix.
        # Reapply the whitelist rather than trusting an exception's arbitrary text.
        reason = str(error).removeprefix(
            "Gemini returned invalid evidence data after one retry: "
        )
        return AnalysisFailure(
            "invalid_model_output",
            "The model returned evidence that failed validation after retry. Retry analysis.",
            _validation_feedback(ValueError(reason)),
        )
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return AnalysisFailure(
            "timeout", "The analysis provider timed out. Retry analysis."
        )
    status = None
    if isinstance(error, APIError):
        status = error.code
    elif isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
    if status in (401, 403):
        return AnalysisFailure(
            "provider_authentication",
            "The analysis provider rejected access. Check the API key and permissions, then retry.",
        )
    if status == 429:
        return AnalysisFailure(
            "provider_rate_limit",
            "The analysis provider reached a rate or quota limit. Check quota and retry later.",
        )
    if status == 404:
        return AnalysisFailure(
            "provider_model_unavailable",
            "The configured analysis model is unavailable. Check the model configuration, then retry.",
        )
    if isinstance(status, int) and 500 <= status < 600:
        return AnalysisFailure(
            "provider_unavailable",
            "The analysis provider is temporarily unavailable. Retry later.",
        )
    return AnalysisFailure(
        "analysis_failed", "Analysis could not be completed. Retry analysis."
    )
