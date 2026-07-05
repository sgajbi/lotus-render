from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class RenderAttemptStatus(StrEnum):
    ACCEPTED = "accepted"
    VALIDATING_PACKAGE = "validating_package"
    RENDERING = "rendering"
    RENDERED = "rendered"
    FAILED = "failed"


class RenderFailureCategory(StrEnum):
    PACKAGE_VALIDATION_FAILED = "package_validation_failed"
    TEMPLATE_NOT_SUPPORTED = "template_not_supported"
    TEMPLATE_RENDER_FAILED = "template_render_failed"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    ARTIFACT_VALIDATION_FAILED = "artifact_validation_failed"
    TIMEOUT = "timeout"
    OPERATOR_INTERVENTION_REQUIRED = "operator_intervention_required"


@dataclass(slots=True)
class RenderAttempt:
    render_job_id: str
    report_job_id: str
    attempt_number: int
    template_id: str
    template_version: str
    output_format: str
    status: RenderAttemptStatus = RenderAttemptStatus.ACCEPTED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    artifact_sha256: str | None = None
    failure_category: RenderFailureCategory | None = None
    diagnostic_summary: str | None = None

    def mark_validating_package(self) -> None:
        self.status = RenderAttemptStatus.VALIDATING_PACKAGE
        self.updated_at = datetime.now(UTC)

    def mark_rendering(self) -> None:
        self.status = RenderAttemptStatus.RENDERING
        self.updated_at = datetime.now(UTC)

    def mark_rendered(self, artifact_sha256: str) -> None:
        self.status = RenderAttemptStatus.RENDERED
        self.artifact_sha256 = artifact_sha256
        self.failure_category = None
        self.diagnostic_summary = None
        self.updated_at = datetime.now(UTC)

    def mark_failed(
        self,
        failure_category: RenderFailureCategory,
        diagnostic_summary: str,
    ) -> None:
        self.status = RenderAttemptStatus.FAILED
        self.failure_category = failure_category
        self.diagnostic_summary = diagnostic_summary
        self.updated_at = datetime.now(UTC)
