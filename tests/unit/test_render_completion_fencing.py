"""Only the winning claim may commit output, return bytes as the artifact, or record custody.

The stale-takeover recovery (#105) means two attempts can hold the same job in
sequence. Before #313 the loser could return its own bytes under the winner's
metadata, deliver those bytes to Archive, and overwrite the winner's custody --
Report records both the artifact hash and the Archive IDs it is given, so the
mismatch would propagate into governed receipts.

Every test here runs the real production path: two independent ``RenderStore``
adapters over one SQLite file (separate connections, exactly like two workers or a
restart), the real ``RenderSubmissionService.submit``, and a recording Archive
transport per worker. The takeover is driven from inside the old worker's render
call, which is where a stalled worker actually loses its job.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.domain.render_attempts.models import RenderAttempt
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.infrastructure.migrations.render_store import (
    _MIGRATIONS,
    CURRENT_RENDER_STORE_SCHEMA_VERSION,
)
from app.infrastructure.render_store import RenderJobTransitionError, RenderStore
from app.services.archive_handoff import ArchiveHandoff, normalize_sha256
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_ports import RenderRuntimeMetadata
from app.services.render_submission import RenderSubmissionService

STALE_SECONDS = 900
REFERENCE = "LOTUS-SG-PF-001-2026-08-31-PRV1-7F3A"

WINNING_BYTES = b"%PDF-1.7\n% the winning attempt's artifact"
LOSING_BYTES = b"%PDF-1.7\n% the stalled attempt's different artifact"


def _package(render_job_id: str) -> RenderPackage:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    payload["render_job_id"] = render_job_id
    payload["render_context"] = {
        "timezone": "Asia/Singapore",
        "document_reference": REFERENCE,
        "archive": {
            "report_request_id": "req_2026_09_13_0001",
            "portfolio_id": "PF-001",
            "as_of_date": "2026-08-31",
            "classification": "confidential",
            "region": "SG",
            "tenant_id": "tenant-alpha",
        },
    }
    return RenderPackage.model_validate(payload)


class _ScriptedEngine:
    """Returns exact bytes; optionally runs a hook mid-render, where takeovers happen."""

    def __init__(self, artifact_bytes: bytes, on_render: Callable[[], None] | None = None) -> None:
        self._artifact_bytes = artifact_bytes
        self._on_render = on_render

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(runtime_engine="typst", runtime_engine_version="0.14.2")

    def render(self, render_package: RenderPackage) -> RenderResult:
        if self._on_render is not None:
            self._on_render()
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
                template_publication="published",
                artifact_sha256=hashlib.sha256(self._artifact_bytes).hexdigest(),
                mime_type="application/pdf",
                output_size_bytes=len(self._artifact_bytes),
                render_duration_ms=5,
            ),
            artifact_bytes=self._artifact_bytes,
        )


class _RecordingTransport:
    """Answers success and remembers every delivery, so 'zero Archive calls' is checkable."""

    def __init__(self, document_id: str) -> None:
        self._document_id = document_id
        self.deliveries: list[dict[str, Any]] = []

    def post_document(self, payload: Any, *, headers: Any) -> tuple[int, dict[str, Any]]:
        self.deliveries.append(dict(payload))
        return 201, {"document_id": self._document_id}


def _worker(
    db_path: Path,
    artifact_bytes: bytes,
    *,
    document_id: str,
    on_render: Callable[[], None] | None = None,
    engine: object | None = None,
) -> tuple[RenderSubmissionService, RenderStore, _RecordingTransport]:
    store = RenderStore(db_path)
    transport = _RecordingTransport(document_id)
    service = RenderSubmissionService(
        render_store=store,
        render_engine=engine or _ScriptedEngine(artifact_bytes, on_render),  # type: ignore[arg-type]
        rendering_stale_seconds=STALE_SECONDS,
        execution_limiter=RenderExecutionLimiter(2),
        archive_handoff=ArchiveHandoff(
            transport,
            render_service_version="0.1.0",
            max_attempts=1,
            retry_backoff_seconds=0,
            sleep=lambda _: None,
        ),
    )
    return service, store, transport


def _age_job(db_path: Path, render_job_id: str, *, seconds: int = STALE_SECONDS + 1) -> None:
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.execute(
            "UPDATE render_job SET updated_at = ? WHERE render_job_id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z"),
                render_job_id,
            ),
        )


def test_a_losing_completion_adopts_the_winner_and_returns_no_foreign_bytes(
    tmp_path: Path,
) -> None:
    """Different bytes: the loser returns the winner's metadata WITHOUT its own bytes,
    makes zero Archive calls, and the winner's custody record stands untouched."""

    db_path = tmp_path / "render-store.sqlite3"
    package = _package("rdr_fence_different_bytes")
    new_service, _, new_transport = _worker(db_path, WINNING_BYTES, document_id="doc_winner")

    def takeover() -> None:
        _age_job(db_path, package.render_job_id)
        response = new_service.submit(package)
        assert response.status == "rendered"

    old_service, store, old_transport = _worker(
        db_path, LOSING_BYTES, document_id="doc_loser", on_render=takeover
    )

    response = old_service.submit(package)

    winning_sha = hashlib.sha256(WINNING_BYTES).hexdigest()
    assert response.status == "rendered"
    assert response.artifact_sha256 is not None
    assert normalize_sha256(response.artifact_sha256) == winning_sha
    assert response.artifact_base64 is None, (
        "bytes that do not hash to the returned digest must be withheld"
    )
    assert response.archive_document_id == "doc_winner"
    assert old_transport.deliveries == [], "the losing attempt must make zero Archive calls"
    assert len(new_transport.deliveries) == 1
    stored = store.get(package.render_job_id)
    assert stored.artifact_sha256 == f"sha256:{winning_sha}"
    assert stored.archive_document_id == "doc_winner", "winning custody must be stable"
    assert stored.claim_generation == 2


def test_a_losing_completion_with_identical_bytes_returns_the_winning_artifact(
    tmp_path: Path,
) -> None:
    """Same bytes: under bounded determinism the loser's bytes ARE the winning artifact,
    so they may be returned -- but custody still belongs to the winner alone."""

    db_path = tmp_path / "render-store.sqlite3"
    package = _package("rdr_fence_identical_bytes")
    new_service, _, new_transport = _worker(db_path, WINNING_BYTES, document_id="doc_winner")

    def takeover() -> None:
        _age_job(db_path, package.render_job_id)
        new_service.submit(package)

    old_service, store, old_transport = _worker(
        db_path, WINNING_BYTES, document_id="doc_loser", on_render=takeover
    )

    response = old_service.submit(package)

    assert response.status == "rendered"
    assert response.artifact_base64 is not None
    returned = base64.b64decode(response.artifact_base64)
    assert response.artifact_sha256 is not None
    assert hashlib.sha256(returned).hexdigest() == normalize_sha256(response.artifact_sha256), (
        "returned bytes must hash to the returned digest"
    )
    assert old_transport.deliveries == [], "identical bytes still do not license a second handoff"
    assert len(new_transport.deliveries) == 1
    assert store.get(package.render_job_id).archive_document_id == "doc_winner"


def test_an_old_completion_after_takeover_cannot_beat_the_live_claim(tmp_path: Path) -> None:
    """The claim carries a generation, so an old worker finishing first after losing its
    job cannot win a status-only completion: the live claim's render still lands."""

    db_path = tmp_path / "render-store.sqlite3"
    package = _package("rdr_fence_live_claim")
    new_store = RenderStore(db_path)
    claims: list[int] = []

    def takeover_without_completion() -> None:
        _age_job(db_path, package.render_job_id)
        claimed = new_store.claim_for_rendering(
            package.render_job_id, rendering_stale_seconds=STALE_SECONDS
        )
        assert claimed is not None
        claims.append(claimed.claim_generation)

    old_service, _, old_transport = _worker(
        db_path, LOSING_BYTES, document_id="doc_loser", on_render=takeover_without_completion
    )

    response = old_service.submit(package)

    assert response.status == "rendering", (
        "the job belongs to the live claim; the old attempt reports that truth"
    )
    assert response.artifact_base64 is None
    assert response.artifact_sha256 is None
    assert old_transport.deliveries == []
    row = new_store.get(package.render_job_id)
    assert row.status == "rendering"
    assert row.claim_generation == claims[0], "the live claim must survive the old completion"

    winner_engine = _ScriptedEngine(WINNING_BYTES)
    completed = new_store.mark_rendered(
        package.render_job_id,
        winner_engine.render(package),
        claim_generation=claims[0],
    )
    assert completed.status == "rendered"
    assert completed.artifact_sha256 == f"sha256:{hashlib.sha256(WINNING_BYTES).hexdigest()}"


def test_a_late_failure_cannot_overwrite_the_live_claim(tmp_path: Path) -> None:
    """An old attempt failing after takeover must not move the new claim to 'failed' --
    before #313, mark_failed accepted 'rendering' regardless of who owned it."""

    db_path = tmp_path / "render-store.sqlite3"
    package = _package("rdr_fence_late_failure")
    new_store = RenderStore(db_path)
    claims: list[int] = []

    def takeover_then_fail() -> None:
        _age_job(db_path, package.render_job_id)
        claimed = new_store.claim_for_rendering(
            package.render_job_id, rendering_stale_seconds=STALE_SECONDS
        )
        assert claimed is not None
        claims.append(claimed.claim_generation)
        raise RuntimeError("old worker dies late")

    old_service, _, old_transport = _worker(
        db_path, LOSING_BYTES, document_id="doc_loser", on_render=takeover_then_fail
    )

    response = old_service.submit(package)

    assert response.status == "rendering", "the late failure adopted the live claim's truth"
    assert response.failure_category is None
    assert old_transport.deliveries == []
    row = new_store.get(package.render_job_id)
    assert row.status == "rendering", "the live claim must not be failed by a stale attempt"
    assert row.claim_generation == claims[0]


def test_a_late_failure_cannot_overwrite_the_winner(tmp_path: Path) -> None:
    """An old attempt failing after the new attempt already rendered must adopt the
    winner's terminal truth rather than raising or rewriting it."""

    db_path = tmp_path / "render-store.sqlite3"
    package = _package("rdr_fence_late_failure_terminal")
    new_service, _, new_transport = _worker(db_path, WINNING_BYTES, document_id="doc_winner")

    def takeover_then_fail() -> None:
        _age_job(db_path, package.render_job_id)
        new_service.submit(package)
        raise RuntimeError("old worker dies after the winner completed")

    old_service, store, old_transport = _worker(
        db_path, LOSING_BYTES, document_id="doc_loser", on_render=takeover_then_fail
    )

    response = old_service.submit(package)

    assert response.status == "rendered"
    assert response.failure_category is None
    assert response.archive_document_id == "doc_winner"
    assert old_transport.deliveries == []
    assert len(new_transport.deliveries) == 1
    stored = store.get(package.render_job_id)
    assert stored.status == "rendered"
    assert stored.archive_document_id == "doc_winner"


def test_custody_writes_are_fenced_to_the_winning_generation(tmp_path: Path) -> None:
    """The custody columns are keyed by job id; without the generation fence any late
    writer could replace the winner's Archive identity."""

    db_path = tmp_path / "render-store.sqlite3"
    package = _package("rdr_fence_custody")
    service, store, _ = _worker(db_path, WINNING_BYTES, document_id="doc_winner")
    response = service.submit(package)
    assert response.archive_document_id == "doc_winner"
    winning_generation = store.get(package.render_job_id).claim_generation

    with pytest.raises(RenderJobTransitionError, match="stale_archive_outcome_write"):
        store.record_archive_outcome(
            package.render_job_id,
            archive_state="archived_verified",
            archive_document_id="doc_loser",
            archive_request_id="areq_loser",
            archive_detail=None,
            expected_claim_generation=winning_generation - 1,
        )

    stored = store.get(package.render_job_id)
    assert stored.archive_document_id == "doc_winner", "stale custody write must not land"

    refreshed = store.record_archive_outcome(
        package.render_job_id,
        archive_state="archived_verified",
        archive_document_id="doc_winner",
        archive_request_id=stored.archive_request_id,
        archive_detail=None,
        expected_claim_generation=winning_generation,
    )
    assert refreshed.archive_document_id == "doc_winner"


def test_restart_preserves_the_fence_against_a_pre_restart_zombie(tmp_path: Path) -> None:
    """A restart changes nothing about ownership: a claim taken before the restart is
    fenced out once a post-restart submission reclaims the stale job."""

    db_path = tmp_path / "render-store.sqlite3"
    package = _package("rdr_fence_restart")
    pre_restart_store = RenderStore(db_path)
    pre_restart_store.create_or_get(
        render_job_id=package.render_job_id,
        report_job_id=package.report_job_id,
        render_package_version=package.render_package_version,
        package_hash="hash-restart-irrelevant",
        report_type=package.report_type,
        template_id=package.template_id,
        template_version=package.template_version,
        output_format=package.output_format,
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
    )
    zombie_claim = pre_restart_store.claim_for_rendering(
        package.render_job_id, rendering_stale_seconds=STALE_SECONDS
    )
    assert zombie_claim is not None
    _age_job(db_path, package.render_job_id)

    # The restart: a fresh adapter (new connections) reclaims and completes the job.
    post_restart_store = RenderStore(db_path)
    reclaimed = post_restart_store.claim_for_rendering(
        package.render_job_id, rendering_stale_seconds=STALE_SECONDS
    )
    assert reclaimed is not None
    assert reclaimed.claim_generation == zombie_claim.claim_generation + 1
    winner = _ScriptedEngine(WINNING_BYTES).render(package)
    post_restart_store.mark_rendered(
        package.render_job_id, winner, claim_generation=reclaimed.claim_generation
    )

    zombie_result = _ScriptedEngine(LOSING_BYTES).render(package)
    with pytest.raises(RenderJobTransitionError):
        pre_restart_store.mark_rendered(
            package.render_job_id, zombie_result, claim_generation=zombie_claim.claim_generation
        )
    with pytest.raises(RenderJobTransitionError):
        pre_restart_store.mark_failed(
            render_job_id=package.render_job_id,
            failure_category="timeout",
            failure_message="zombie timeout",
            claim_generation=zombie_claim.claim_generation,
        )
    stored = post_restart_store.get(package.render_job_id)
    assert stored.status == "rendered"
    assert stored.artifact_sha256 == f"sha256:{hashlib.sha256(WINNING_BYTES).hexdigest()}"


def test_a_legacy_rendering_row_is_claimable_and_fenced_after_upgrade(tmp_path: Path) -> None:
    """Pre-upgrade rows have no generation column. After migration they carry 0, stay
    claimable through the ordinary stale takeover, and fence exactly like new rows --
    the platform's stateful-migration bar: no state the new runtime neither claims
    nor recovers."""

    db_path = tmp_path / "render-store.sqlite3"
    with closing(sqlite3.connect(db_path)) as connection, connection:
        for version, migration in _MIGRATIONS:
            if version > 5:
                break
            migration(connection)
        connection.execute("PRAGMA user_version = 5")
        connection.execute(
            """
            INSERT INTO render_job (
                render_job_id, report_job_id, render_package_version, package_hash,
                report_type, template_id, template_version, output_format, status,
                runtime_engine, runtime_engine_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "rdr_legacy_in_flight",
                "rjob_legacy",
                "render_package.v1",
                "hash-legacy",
                "portfolio_review",
                "portfolio-review",
                "v1",
                "pdf",
                "rendering",
                "typst",
                "0.14.2",
                "2026-07-05T00:00:00Z",
                "2026-07-05T00:00:00Z",
            ),
        )

    store = RenderStore(db_path)
    store.check_ready()
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (
            CURRENT_RENDER_STORE_SCHEMA_VERSION
        )

    legacy = store.get("rdr_legacy_in_flight")
    assert legacy.claim_generation == 0

    claimed = store.claim_for_rendering(
        "rdr_legacy_in_flight", rendering_stale_seconds=STALE_SECONDS
    )
    assert claimed is not None, "a stale legacy in-flight row must remain recoverable"
    assert claimed.claim_generation == 1

    zombie = _ScriptedEngine(LOSING_BYTES).render(_package("rdr_legacy_in_flight"))
    with pytest.raises(RenderJobTransitionError, match="stale_render_claim"):
        store.mark_rendered("rdr_legacy_in_flight", zombie, claim_generation=0)

    winner = _ScriptedEngine(WINNING_BYTES).render(_package("rdr_legacy_in_flight"))
    completed = store.mark_rendered(
        "rdr_legacy_in_flight", winner, claim_generation=claimed.claim_generation
    )
    assert completed.status == "rendered"
