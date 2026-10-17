from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / "backend/.env", extra="ignore", env_prefix=""
    )
    data_dir: Path = ROOT / "data"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    analysis_mode: str = Field(default="auto", validation_alias="REWIND_ANALYSIS_MODE")
    max_file_bytes: int = Field(default=250 * 1024 * 1024, gt=0)
    max_request_bytes: int = Field(default=500 * 1024 * 1024, gt=0)
    max_files: int = Field(default=12, ge=1)
