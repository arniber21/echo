"""Bounded Gemini Files API lifecycle and schema-constrained generation."""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from .types import AnalysisSettings

Model = TypeVar("Model", bound=BaseModel)
logger = logging.getLogger(__name__)


class InvalidModelOutput(ValueError):
    """The provider failed schema or evidence validation twice."""


class GeminiProvider:
    def __init__(self, settings: AnalysisSettings):
        self.settings = settings
        self.client = genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(timeout=int(settings.request_timeout_seconds * 1000)),
        )

    async def close(self) -> None:
        await self.client.aio.aclose()

    async def generate(
        self,
        prompt: str,
        schema: type[Model],
        *,
        path: Path | None = None,
        mime_type: str | None = None,
        validate: Callable[[Model], None] | None = None,
    ) -> Model:
        uploaded_name: str | None = None
        contents: list[types.Part] = []
        try:
            if path is not None:
                async with asyncio.timeout(self.settings.upload_timeout_seconds):
                    uploaded = await self.client.aio.files.upload(
                        file=path, config=types.UploadFileConfig(mime_type=mime_type)
                    )
                    uploaded_name = uploaded.name
                    while uploaded.state and uploaded.state.name == "PROCESSING":
                        await asyncio.sleep(1)
                        uploaded = await self.client.aio.files.get(name=uploaded_name)
                    if uploaded.state and uploaded.state.name == "FAILED":
                        raise RuntimeError("Gemini could not process the media file")
                    if not uploaded.uri:
                        raise RuntimeError("Gemini returned a file without a URI")
                    contents.append(types.Part.from_uri(
                        file_uri=uploaded.uri, mime_type=mime_type or uploaded.mime_type
                    ))
            for attempt in range(2):
                instruction = prompt
                if attempt:
                    instruction += "\nYour previous answer failed validation. Return complete valid JSON satisfying every schema and evidence constraint."
                async with asyncio.timeout(self.settings.request_timeout_seconds):
                    response = await self.client.aio.models.generate_content(
                        model=self.settings.model,
                        contents=[*contents, types.Part.from_text(text=instruction)],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                            temperature=0,
                        ),
                    )
                try:
                    result = schema.model_validate_json(response.text or "")
                    if validate is not None:
                        validate(result)
                    return result
                except (ValueError, ValidationError):
                    if attempt == 1:
                        raise InvalidModelOutput("Gemini returned invalid evidence data after one retry") from None
            raise AssertionError("unreachable")
        finally:
            if uploaded_name:
                try:
                    async with asyncio.timeout(15):
                        await self.client.aio.files.delete(name=uploaded_name)
                except Exception:
                    logger.warning("Could not delete temporary Gemini file; provider retention policy applies")
