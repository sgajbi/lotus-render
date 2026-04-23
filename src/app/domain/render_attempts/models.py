from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class RenderAttemptStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RenderFailureCategory(StrEnum):
    PACKAGE_INVALID = "package_invalid"
    TEMPLATE_INCOMPATIBLE = "template_incompatible"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    RENDER_RUNTIME_FAILURE = "render_runtime_failure"


@dataclass(slots=True)
class RenderAttempt:
    render_job_id: str
    report_job_id: str
    attempt_number: int
    template_id: str
    template_version: str
    output_format: str
    status: RenderAttemptStatus = RenderAttemptStatus.ACCEPTED
    created_at: datetime = datetime.now(UTC)
    updated_at: datetime = datetime.now(UTC)
    artifact_sha256: str | None = None
    failure_category: RenderFailureCategory | None = None
    diagnostic_summary: str | None = None

    def mark_running(self) -> None:
        self.status = RenderAttemptStatus.RUNNING
        self.updated_at = datetime.now(UTC)

    def mark_succeeded(self, artifact_sha256: str) -> None:
        self.status = RenderAttemptStatus.SUCCEEDED
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
