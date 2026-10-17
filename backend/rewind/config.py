from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / "backend/.env",
        extra="ignore",
        env_prefix="",
        populate_by_name=True,
    )
    data_dir: Path = ROOT / "data"
    photon_base_url: str = "https://photon.komoot.io"
    seed_demo: bool = Field(default=False, validation_alias="REWIND_SEED_DEMO")
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    typesafe_api_key: SecretStr | None = None
    typesafe_model: str = "jev-1.14.0"
    typesafe_enabled: bool = Field(
        default=True, validation_alias="REWIND_TYPESAFE_ENABLED"
    )
    typesafe_max_frames: int = Field(
        default=8, ge=1, le=24, validation_alias="REWIND_TYPESAFE_MAX_FRAMES"
    )
    analysis_mode: Literal["auto", "mock", "live"] = Field(
        default="auto", validation_alias="REWIND_ANALYSIS_MODE"
    )
    max_file_bytes: int = Field(default=250 * 1024 * 1024, gt=0)
    max_request_bytes: int = Field(default=500 * 1024 * 1024, gt=0)
    max_files: int = Field(default=12, ge=1)
