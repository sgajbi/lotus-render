from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = Field(default="lotus-render")
    service_version: str = Field(default="0.1.0")
    rounding_policy_version: str = Field(default="v1")
    environment: str = Field(default="development")
    default_output_format: str = Field(default="pdf")
    runtime_engine: str = Field(default="typst")
    runtime_engine_version: str = Field(default="0.14.2")
    supported_output_formats: tuple[str, ...] = Field(default=("pdf",))
    template_registry_path: str = Field(default="templates/registry")
    render_store_path: str = Field(default="data/render-store.sqlite3")
    allowed_hosts: tuple[str, ...] = Field(
        default=("localhost", "127.0.0.1", "testserver", "lotus-render")
    )
    cors_allowed_origins: tuple[str, ...] = Field(default=())
    max_request_body_bytes: int = Field(default=5_242_880, ge=1)
    render_compile_timeout_seconds: int = Field(default=60, ge=1)
    render_execution_concurrency_limit: int = Field(default=2, ge=1)
    stale_accepted_seconds: int = Field(default=300, ge=1)
    stale_rendering_seconds: int = Field(default=900, ge=1)
    require_persistent_render_store: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix="LOTUS_RENDER_",
        env_file=".env",
        extra="ignore",
    )

    @field_validator(
        "service_name",
        "service_version",
        "rounding_policy_version",
        "environment",
        "default_output_format",
        "runtime_engine",
        "runtime_engine_version",
        "template_registry_path",
        "render_store_path",
    )
    @classmethod
    def _non_blank_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("supported_output_formats", "allowed_hosts", "cors_allowed_origins")
    @classmethod
    def _non_blank_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values if value.strip())
        if len(normalized) != len(values):
            raise ValueError("configuration values must not be blank")
        return normalized

    @model_validator(mode="after")
    def _validate_runtime_contract(self) -> "Settings":
        if self.default_output_format not in self.supported_output_formats:
            raise ValueError("default_output_format must be included in supported_output_formats")
        if "pdf" not in self.supported_output_formats:
            raise ValueError("pdf output support is required for lotus-render")
        if self.require_persistent_render_store and self.render_store_path == ":memory:":
            raise ValueError("persistent render store is required for this environment")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
