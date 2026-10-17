"""Content-addressed JSON cache; corrupt entries are treated as misses."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypeVar

from pydantic import BaseModel, ValidationError

Model = TypeVar("Model", bound=BaseModel)


def cache_key(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class JsonCache:
    def __init__(self, directory: Path):
        self.directory = directory

    def read(self, key: str, schema: type[Model]) -> Model | None:
        try:
            return schema.model_validate_json(
                (self.directory / f"{key}.json").read_text()
            )
        except (OSError, ValueError, ValidationError):
            return None

    def write(self, key: str, result: BaseModel) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with NamedTemporaryFile(
                mode="w", dir=self.directory, delete=False
            ) as stream:
                temporary = stream.name
                stream.write(result.model_dump_json())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / f"{key}.json")
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
