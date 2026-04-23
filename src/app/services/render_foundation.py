from __future__ import annotations

from typing import TypedDict

from app.core.settings import Settings
from app.domain.render_attempts.models import RenderAttemptStatus


class FoundationMetadata(TypedDict):
    service: str
    version: str
    roundingPolicyVersion: str
    environment: str
    runtimeEngine: str
    runtimeEngineVersion: str
    defaultOutputFormat: str
    supportedOutputFormats: list[str]
    renderAttemptStatuses: list[str]


class RenderFoundationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def readiness_status(
        self,
        *,
        is_draining: bool,
        render_store_ready: bool,
    ) -> tuple[int, dict[str, str]]:
        if is_draining:
            return 503, {"status": "draining"}
        if not self._settings.supported_output_formats:
            return 503, {"status": "not_ready"}
        if not render_store_ready:
            return 503, {"status": "not_ready"}
        return 200, {"status": "ready"}

    def metadata(self) -> FoundationMetadata:
        return {
            "service": self._settings.service_name,
            "version": self._settings.service_version,
            "roundingPolicyVersion": self._settings.rounding_policy_version,
            "environment": self._settings.environment,
            "runtimeEngine": self._settings.runtime_engine,
            "runtimeEngineVersion": self._settings.runtime_engine_version,
            "defaultOutputFormat": self._settings.default_output_format,
            "supportedOutputFormats": list(self._settings.supported_output_formats),
            "renderAttemptStatuses": [status.value for status in RenderAttemptStatus],
        }
