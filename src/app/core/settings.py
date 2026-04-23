from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = Field(default="lotus-render")
    service_version: str = Field(default="0.1.0")
    rounding_policy_version: str = Field(default="v1")
    environment: str = Field(default="development")
    default_output_format: str = Field(default="pdf")
    runtime_engine: str = Field(default="typst")
    runtime_engine_version: str = Field(default="foundation")
    supported_output_formats: tuple[str, ...] = Field(default=("pdf",))

    model_config = SettingsConfigDict(
        env_prefix="LOTUS_RENDER_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
