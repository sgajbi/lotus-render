"""The custody truth reaches the caller and the store; the render is never hostage.

Submission-level proof of the #120 wiring: whatever Archive answers -- verified,
pending, refused, unreachable, or the handoff code itself crashing -- the job stays
'rendered', the artifact is still returned, and the archive fields on both the submit
response and the status endpoint state exactly what was observed. Null means "no
handoff applies", which is why the unconfigured deployment and the pre-cutover
package both stay null rather than inventing a failure.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.domain.render_attempts.models import RenderAttempt
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.infrastructure.render_store import RenderStore, StoredRenderJob
from app.services.archive_handoff import (
    ArchiveDeliveryNotSentError,
    ArchiveHandoff,
    ArchiveOutcomeUnknownError,
    derive_archive_request_id,
)
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_ports import RenderRuntimeMetadata
from app.services.render_submission import RenderSubmissionService

ARTIFACT = b"%PDF-1.7\n% governed artifact bytes"
ARTIFACT_SHA = hashlib.sha256(ARTIFACT).hexdigest()
REFERENCE = "LOTUS-SG-PF-001-2026-08-31-PRV1-7F3A"

CUSTODY = {
    "report_request_id": "req_2026_09_04_0001",
    "portfolio_scope": '{"portfolio_ids":["PF-001"]}',
    "portfolio_id": "PF-001",
    "as_of_date": "2026-08-31",
    "reporting_period_start": "2026-01-01",
    "reporting_period_end": "2026-08-31",
    "frequency": "ad_hoc",
    "classification": "confidential",
    "region": "SG",
    "tenant_id": "tenant-alpha",
}


def _package(with_custody: bool) -> RenderPackage:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    if with_custody:
        payload["render_context"] = {
            "timezone": "Asia/Singapore",
            "document_reference": REFERENCE,
            "archive": dict(CUSTODY),
        }
    return RenderPackage.model_validate(payload)


class _RenderingEngine:
    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(runtime_engine="typst", runtime_engine_version="0.14.2")

    def render(self, render_package: RenderPackage) -> RenderResult:
        return RenderResult(
            attempt=RenderAttempt(
                render_job_id=render_package.render_job_id,
                report_job_id=render_package.report_job_id,
                attempt_number=1,
                template_id=render_package.template_id,
                template_version=render_package.template_version,
                output_format=render_package.output_format,
            ),
            diagnostic=RenderDiagnostic(
                render_job_id=render_package.render_job_id,
                render_package_version=render_package.render_package_version,
                template_id=render_package.template_id,
                template_version=render_package.template_version,
                runtime_engine="typst",
                runtime_engine_version="0.14.2",
                output_format=render_package.output_format,
                status="rendered",
                determinism_mode="bounded",
                determinism_statement="bounded determinism",
                bounded_determinism_fingerprint="typst-0.14.2:test",
                template_digest="sha256:feedbeef",
                artifact_sha256=ARTIFACT_SHA,
                mime_type="application/pdf",
                output_size_bytes=len(ARTIFACT),
                render_duration_ms=5,
            ),
            artifact_bytes=ARTIFACT,
        )


class _ScriptedTransport:
    def __init__(self, *script: tuple[int, dict[str, Any]] | Exception) -> None:
        self._script = list(script)
        self.calls = 0

    def post_document(self, payload: Any, *, headers: Any) -> tuple[int, dict[str, Any]]:
        self.calls += 1
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _service(
    tmp_path: Path, transport: _ScriptedTransport | None
) -> tuple[RenderSubmissionService, Path]:
    store_path = tmp_path / "render-store.sqlite3"
    handoff = None
    if transport is not None:
        handoff = ArchiveHandoff(
            transport,
            render_service_version="0.1.0",
            max_attempts=2,
            retry_backoff_seconds=0,
            sleep=lambda _: None,
        )
    service = RenderSubmissionService(
        render_store=RenderStore(store_path),
        rendering_stale_seconds=900,
        execution_limiter=RenderExecutionLimiter(2),
        render_engine=_RenderingEngine(),
        archive_handoff=handoff,
    )
    return service, store_path


def test_verified_custody_reaches_the_response_and_survives_a_restart(
    tmp_path: Path,
) -> None:
    transport = _ScriptedTransport((201, {"document_id": "doc_ab12"}))
    service, store_path = _service(tmp_path, transport)

    response = service.submit(_package(with_custody=True))

    assert response.status == "rendered"
    assert response.artifact_base64 is not None, "custody must never withhold the artifact"
    assert response.archive_state == "archived_verified"
    assert response.archive_document_id == "doc_ab12"
    assert response.archive_request_id == derive_archive_request_id(REFERENCE, ARTIFACT_SHA), (
        "consumers read the delivery identity from here; nobody re-derives it"
    )

    # A fresh store over the same file is the restart: the truth was persisted, not held.
    reopened = RenderStore(store_path)
    stored = reopened.get("rdr_golden_portfolio_review_v1")
    assert stored.archive_state == "archived_verified"
    assert stored.archive_document_id == "doc_ab12"
    assert stored.archive_request_id == derive_archive_request_id(REFERENCE, ARTIFACT_SHA)

    status = service.get_status("rdr_golden_portfolio_review_v1")
    assert status.archive_state == "archived_verified"
    assert status.archive_document_id == "doc_ab12"
    assert response.archive_detail is None and status.archive_detail is None, (
        "verified custody carries no refusal words to misread"
    )


def test_an_unreachable_archive_never_fails_the_render(tmp_path: Path) -> None:
    transport = _ScriptedTransport(
        ArchiveDeliveryNotSentError("refused"), ArchiveDeliveryNotSentError("refused")
    )
    service, store_path = _service(tmp_path, transport)

    response = service.submit(_package(with_custody=True))

    assert response.status == "rendered"
    assert response.artifact_base64 is not None
    assert response.archive_state == "archive_failed"
    assert response.archive_document_id is None
    # Report maps retry posture from Archive's words, so the caller-facing surfaces
    # must carry them -- an unreachable Archive is retry-eligible, a checksum
    # refusal is not, and archive_state alone cannot say which.
    assert response.archive_detail is not None
    assert "archive_unreachable" in response.archive_detail
    stored = RenderStore(store_path).get("rdr_golden_portfolio_review_v1")
    assert stored.archive_detail is not None
    assert "archive_unreachable" in stored.archive_detail


def test_a_timeout_leaves_the_reconciliation_key_on_the_job(tmp_path: Path) -> None:
    """archive_pending is only honest if an operator can actually reconcile: the
    derived request id must be on the job even though no response ever arrived."""

    transport = _ScriptedTransport(TimeoutError("deadline"))
    service, store_path = _service(tmp_path, transport)

    response = service.submit(_package(with_custody=True))

    assert response.status == "rendered"
    assert response.archive_state == "archive_pending"
    assert response.archive_request_id == derive_archive_request_id(REFERENCE, ARTIFACT_SHA), (
        "pending is only honest if the caller holds the reconciliation key"
    )
    assert response.archive_detail is not None
    assert "reconcile" in response.archive_detail
    stored = RenderStore(store_path).get("rdr_golden_portfolio_review_v1")
    assert stored.archive_request_id == derive_archive_request_id(REFERENCE, ARTIFACT_SHA)


def test_a_handoff_crash_is_contained_and_named(tmp_path: Path) -> None:
    """A bug in the handoff code itself must not take the render down with it --
    the job records a named failure instead of the exception propagating."""

    transport = _ScriptedTransport(RuntimeError("nobody expects this"))
    service, _ = _service(tmp_path, transport)

    response = service.submit(_package(with_custody=True))

    assert response.status == "rendered"
    assert response.artifact_base64 is not None
    assert response.archive_state == "archive_failed"
    stored_detail = service.get_status("rdr_golden_portfolio_review_v1")
    assert stored_detail.archive_state == "archive_failed"


def test_a_package_without_custody_carries_no_archive_state(tmp_path: Path) -> None:
    transport = _ScriptedTransport()
    service, _ = _service(tmp_path, transport)

    response = service.submit(_package(with_custody=False))

    assert response.status == "rendered"
    assert response.archive_state is None
    assert response.archive_document_id is None
    assert transport.calls == 0


def test_an_unconfigured_deployment_records_no_archive_state(tmp_path: Path) -> None:
    service, _ = _service(tmp_path, None)

    response = service.submit(_package(with_custody=True))

    assert response.status == "rendered"
    assert response.archive_state is None
    assert response.archive_document_id is None


class _AmnesiacStore(RenderStore):
    """Delivers custody, then cannot write it down."""

    def record_archive_outcome(self, render_job_id: str, **_: object) -> StoredRenderJob:
        raise sqlite3.OperationalError("database is locked")


def test_a_store_that_cannot_record_custody_still_returns_the_render(
    tmp_path: Path,
) -> None:
    """Best-effort recording, both halves: custody was delivered, the write failed,
    and the caller still gets the artifact with the job's last recorded truth."""

    transport = _ScriptedTransport((201, {"document_id": "doc_ab12"}))
    handoff = ArchiveHandoff(
        transport,
        render_service_version="0.1.0",
        max_attempts=1,
        retry_backoff_seconds=0,
        sleep=lambda _: None,
    )
    service = RenderSubmissionService(
        render_store=_AmnesiacStore(tmp_path / "render-store.sqlite3"),
        rendering_stale_seconds=900,
        execution_limiter=RenderExecutionLimiter(2),
        render_engine=_RenderingEngine(),
        archive_handoff=handoff,
    )

    response = service.submit(_package(with_custody=True))

    assert transport.calls == 1
    assert response.status == "rendered"
    assert response.artifact_base64 is not None
    assert response.archive_state is None, "an unrecorded outcome must not be claimed"


def test_the_factory_builds_the_handoff_only_when_configured(tmp_path: Path) -> None:
    from app.core.settings import Settings
    from app.main import _archive_handoff

    assert _archive_handoff(Settings(render_store_path=str(tmp_path / "s.db"))) is None
    configured = _archive_handoff(
        Settings(
            render_store_path=str(tmp_path / "s.db"),
            archive_base_url="http://archive.test",
        )
    )
    assert isinstance(configured, ArchiveHandoff)


def test_a_connection_lost_after_send_surfaces_as_pending(tmp_path: Path) -> None:
    """The steering's transport discipline at the caller's surface: a reset after
    the request was accepted may sit on top of a committed document, so the job
    says pending with the reconciliation key -- never a definite failure."""

    transport = _ScriptedTransport(ArchiveOutcomeUnknownError("connection reset by peer"))
    service, store_path = _service(tmp_path, transport)

    response = service.submit(_package(with_custody=True))

    assert response.status == "rendered"
    assert response.artifact_base64 is not None
    assert response.archive_state == "archive_pending"
    assert response.archive_request_id == derive_archive_request_id(REFERENCE, ARTIFACT_SHA)
    stored = RenderStore(store_path).get("rdr_golden_portfolio_review_v1")
    assert stored.archive_detail is not None
    assert "archive_outcome_unknown" in stored.archive_detail
