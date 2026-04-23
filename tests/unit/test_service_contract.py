from app.core.settings import Settings
from app.domain.render_attempts.models import (
    RenderAttempt,
    RenderFailureCategory,
)
from app.main import SERVICE_NAME
from app.services.render_foundation import RenderFoundationService


def test_service_name_is_lotus_prefixed() -> None:
    assert SERVICE_NAME.startswith("lotus-")


def test_render_attempt_lifecycle_transitions() -> None:
    attempt = RenderAttempt(
        render_job_id="rdr_123",
        report_job_id="rpt_456",
        attempt_number=1,
        template_id="portfolio-review",
        template_version="v1",
        output_format="pdf",
    )

    assert attempt.status.value == "accepted"
    attempt.mark_running()
    assert attempt.status.value == "running"

    attempt.mark_failed(
        RenderFailureCategory.ENGINE_UNAVAILABLE,
        "typst runtime unavailable",
    )
    assert attempt.status.value == "failed"
    assert attempt.failure_category == RenderFailureCategory.ENGINE_UNAVAILABLE

    attempt.mark_succeeded("abc123")
    assert attempt.status.value == "succeeded"
    assert attempt.artifact_sha256 == "abc123"
    assert attempt.failure_category is None


def test_render_foundation_metadata_exposes_supported_statuses() -> None:
    service = RenderFoundationService(Settings())
    metadata = service.metadata()

    assert metadata["runtimeEngine"] == "typst"
    assert metadata["supportedOutputFormats"] == ["pdf"]
    assert metadata["renderAttemptStatuses"] == [
        "accepted",
        "running",
        "succeeded",
        "failed",
    ]


def test_render_foundation_reports_not_ready_without_supported_formats() -> None:
    service = RenderFoundationService(Settings(supported_output_formats=()))

    status_code, payload = service.readiness_status(is_draining=False)

    assert status_code == 503
    assert payload["status"] == "not_ready"
