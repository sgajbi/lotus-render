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
        default=(
            "localhost",
            "127.0.0.1",
            "testserver",
            "lotus-render",
            "render.dev.lotus",
            "host.docker.internal",
        )
    )
    cors_allowed_origins: tuple[str, ...] = Field(default=())
    max_request_body_bytes: int = Field(default=5_242_880, ge=1)
    render_compile_timeout_seconds: int = Field(default=60, ge=1)
    render_execution_concurrency_limit: int = Field(default=2, ge=1)
    stale_accepted_seconds: int = Field(default=300, ge=1)
    stale_rendering_seconds: int = Field(default=900, ge=1)
    require_persistent_render_store: bool = Field(default=False)
    # lotus-render#120: the evidence-chain handoff to Archive's ONE custody
    # authority. An unset base URL turns the handoff off entirely: jobs carry a
    # null archive state, which means "no handoff applies" -- deliberately
    # distinct from a failed one.
    archive_base_url: str | None = Field(default=None)
    archive_timeout_seconds: float = Field(default=10.0, gt=0)
    archive_max_attempts: int = Field(default=3, ge=1)
    archive_retry_backoff_seconds: float = Field(default=0.5, ge=0)

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

    @property
    def persistent_render_store_required(self) -> bool:
        """Persistence is mandatory outside development; the flag only opts development in.

        POST /renders returns before compilation completes, so accepted jobs live only in
        the store until a bounded worker picks them up. With an in-memory store, a restart
        between acceptance and completion strands every caller polling a job id the service
        no longer knows (issue #83).
        """

        return self.require_persistent_render_store or self.environment != "development"

    @model_validator(mode="after")
    def _validate_runtime_contract(self) -> "Settings":
        if self.default_output_format not in self.supported_output_formats:
            raise ValueError("default_output_format must be included in supported_output_formats")
        if "pdf" not in self.supported_output_formats:
            raise ValueError("pdf output support is required for lotus-render")
        if self.persistent_render_store_required and self.render_store_path == ":memory:":
            raise ValueError(
                "render_store_path=':memory:' loses accepted render jobs on restart and is "
                f"not allowed for environment={self.environment!r}; point "
                "LOTUS_RENDER_RENDER_STORE_PATH at a durable file, or run with "
                "environment='development' if job loss is acceptable"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
