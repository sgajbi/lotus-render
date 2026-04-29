from __future__ import annotations

from typing import Literal, TypedDict

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


RenderSupportabilityState = Literal["ready", "degraded", "unavailable"]
RenderSupportabilityReason = Literal[
    "render_supportability_ready",
    "render_supportability_draining",
    "render_store_unavailable",
    "template_registry_unavailable",
    "runtime_configuration_unavailable",
]
RenderSupportabilityFreshness = Literal["current", "unknown"]
RenderSupportabilityFeatureKey = Literal["render.observability.render_supportability"]


class RenderSupportability(TypedDict):
    featureKey: RenderSupportabilityFeatureKey
    state: RenderSupportabilityState
    reason: RenderSupportabilityReason
    freshnessBucket: RenderSupportabilityFreshness
    deterministicOutputSupported: bool
    runtimeEngine: str
    runtimeEngineVersion: str
    defaultOutputFormat: str
    supportedOutputFormats: list[str]
    renderStoreReady: bool
    templateRegistryReady: bool
    draining: bool


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

    def supportability_status(
        self,
        *,
        is_draining: bool,
        render_store_ready: bool,
        template_registry_ready: bool,
    ) -> RenderSupportability:
        deterministic_output_supported = bool(
            self._settings.runtime_engine
            and self._settings.runtime_engine_version
            and self._settings.default_output_format
            and self._settings.supported_output_formats
        )
        state: RenderSupportabilityState = "ready"
        reason: RenderSupportabilityReason = "render_supportability_ready"
        freshness_bucket: RenderSupportabilityFreshness = "current"

        if is_draining:
            state = "degraded"
            reason = "render_supportability_draining"
        elif not render_store_ready:
            state = "unavailable"
            reason = "render_store_unavailable"
            freshness_bucket = "unknown"
        elif not template_registry_ready:
            state = "unavailable"
            reason = "template_registry_unavailable"
            freshness_bucket = "unknown"
        elif not deterministic_output_supported:
            state = "unavailable"
            reason = "runtime_configuration_unavailable"
            freshness_bucket = "unknown"

        return {
            "featureKey": "render.observability.render_supportability",
            "state": state,
            "reason": reason,
            "freshnessBucket": freshness_bucket,
            "deterministicOutputSupported": deterministic_output_supported,
            "runtimeEngine": self._settings.runtime_engine,
            "runtimeEngineVersion": self._settings.runtime_engine_version,
            "defaultOutputFormat": self._settings.default_output_format,
            "supportedOutputFormats": list(self._settings.supported_output_formats),
            "renderStoreReady": render_store_ready,
            "templateRegistryReady": template_registry_ready,
            "draining": is_draining,
        }

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
