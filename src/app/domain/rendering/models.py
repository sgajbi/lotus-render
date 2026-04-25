from __future__ import annotations

from dataclasses import dataclass

from app.domain.render_attempts.models import RenderAttempt


@dataclass(slots=True)
class RenderDiagnostic:
    render_job_id: str
    render_package_version: str
    template_id: str
    template_version: str
    runtime_engine: str
    runtime_engine_version: str
    output_format: str
    status: str
    determinism_mode: str
    determinism_statement: str
    bounded_determinism_fingerprint: str | None = None
    artifact_sha256: str | None = None
    render_duration_ms: int | None = None
    failure_category: str | None = None
    diagnostic_summary: str | None = None
    mime_type: str | None = None
    output_size_bytes: int | None = None


@dataclass(slots=True)
class RenderResult:
    attempt: RenderAttempt
    diagnostic: RenderDiagnostic
    artifact_bytes: bytes
