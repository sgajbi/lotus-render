"""A render job belongs to the tenant it was admitted under, and to nobody else.

Render is the receiver on the Report -> Render leg of the admitted-tenant contract
(lotus-report#375, Cycle 6 C6-REN-02). Before this slice it admitted no tenant at all:
every read was keyed by the raw job id, and the Archive custody header was copied from
the package body. Now the tenant is transport truth (`X-Tenant-Id`), bound at create,
scoping every read, and carried into custody; the package's custody block is a claim
that may only agree with it.

This is step (a) of the rollout -- admit-if-present. A caller that sends no tenant is
still admitted, because the producer has not started sending one; its job is
unattributed, stays readable, and is never given an owner it did not assert. Refusing
absence is step (c), after lotus-report threads the header on every call.

Every HTTP test runs the registered routes through the app factory with the real
SQLite store; only the render engine is scripted, so no Typst compile is needed.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.dependencies.container import get_render_submission_service
from app.domain.render_attempts.models import RenderAttempt
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.infrastructure.migrations.render_store import _MIGRATIONS
from app.infrastructure.render_store import (
    RenderJobConflictError,
    RenderJobNotFoundError,
    RenderStore,
)
from app.main import create_app
from app.services.archive_handoff import ArchiveHandoff
from app.services.render_execution import RenderExecutionLimiter
from app.services.render_ports import RenderRuntimeMetadata
from app.services.render_submission import RenderSubmissionService

ALPHA = "tenant-alpha"
BETA = "tenant-beta"
ARTIFACT = b"%PDF-1.7\n% admitted-tenant proof"


def _payload(render_job_id: str, *, custody_tenant: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8")
    )
    payload["render_job_id"] = render_job_id
    custody: dict[str, Any] = {
        "report_request_id": "req_2026_09_13_0002",
        "portfolio_id": "PF-001",
        "as_of_date": "2026-08-31",
        "classification": "confidential",
        "region": "SG",
    }
    if custody_tenant is not None:
        custody["tenant_id"] = custody_tenant
    payload["render_context"] = {
        "timezone": "Asia/Singapore",
        "document_reference": "LOTUS-SG-PF-001-2026-08-31-PRV1-7F3B",
        "archive": custody,
    }
    return payload


class _ScriptedEngine:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def runtime_metadata(self) -> RenderRuntimeMetadata:
        return RenderRuntimeMetadata(runtime_engine="typst", runtime_engine_version="0.14.2")

    def render(self, render_package: RenderPackage) -> RenderResult:
        self.calls += 1
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
                artifact_sha256=hashlib.sha256(ARTIFACT).hexdigest(),
                mime_type="application/pdf",
                output_size_bytes=len(ARTIFACT),
                render_duration_ms=5,
            ),
            artifact_bytes=ARTIFACT,
        )


class _RecordingTransport:
    def __init__(self) -> None:
        self.headers: list[dict[str, str]] = []

    def post_document(self, payload: Any, *, headers: Any) -> tuple[int, dict[str, Any]]:
        self.headers.append(dict(headers))
        return 201, {"document_id": "doc_custody"}


def _service(
    store_path: Path, *, transport: _RecordingTransport | None = None
) -> tuple[RenderSubmissionService, _ScriptedEngine]:
    engine = _ScriptedEngine()
    handoff = None
    if transport is not None:
        handoff = ArchiveHandoff(
            transport,
            render_service_version="0.1.0",
            max_attempts=1,
            retry_backoff_seconds=0,
            sleep=lambda _: None,
        )
    service = RenderSubmissionService(
        render_store=RenderStore(store_path),
        render_engine=engine,
        rendering_stale_seconds=900,
        execution_limiter=RenderExecutionLimiter(2),
        archive_handoff=handoff,
    )
    return service, engine


@contextmanager
def _client(store_path: Path) -> Iterator[tuple[TestClient, _ScriptedEngine]]:
    """The registered routes over the real store, with only the engine scripted.

    Entered as a context so the app lifespan runs: that is where the container the
    routes depend on is installed, exactly as in production.
    """
    app = create_app(Settings(render_store_path=str(store_path)))
    service, engine = _service(store_path)
    app.dependency_overrides[get_render_submission_service] = lambda: service
    with TestClient(app) as client:
        yield client, engine


def _tenant(tenant: str | None) -> dict[str, str]:
    return {} if tenant is None else {"X-Tenant-Id": tenant}


def _row_tenant(store_path: Path, render_job_id: str) -> str | None:
    return RenderStore(store_path).get(render_job_id, tenant_id=None).tenant_id


def test_a_job_is_bound_to_the_admitted_tenant_and_invisible_to_another(
    tmp_path: Path,
) -> None:
    """Foreign and absent must be indistinguishable: a 404, not a 403 that confirms
    the job exists."""

    store_path = tmp_path / "render-store.sqlite3"
    job = "rdr_tenant_alpha_owned"
    with _client(store_path) as (client, _):
        created = client.post(
            "/renders", json=_payload(job, custody_tenant=ALPHA), headers=_tenant(ALPHA)
        )
        assert created.status_code == 201, created.text
        assert _row_tenant(store_path, job) == ALPHA

        for path in (
            f"/renders/{job}",
            f"/renders/{job}/diagnostics",
            f"/renders/{job}/artifact-metadata",
        ):
            assert client.get(path, headers=_tenant(ALPHA)).status_code == 200, path
            foreign = client.get(path, headers=_tenant(BETA))
            assert foreign.status_code == 404, path
            assert foreign.json()["detail"]["code"] == "render_job_not_found"
            absent = client.get(path.replace(job, "rdr_never_existed"), headers=_tenant(BETA))
            assert absent.json() == foreign.json(), "foreign must look exactly like absent"


def test_a_contradicting_custody_tenant_is_refused_before_any_effect(tmp_path: Path) -> None:
    """The header is authority and the body is a claim; when they disagree nothing
    downstream can choose, so the request is refused before create, claim, compile
    or Archive -- and the store shows it never happened."""

    store_path = tmp_path / "render-store.sqlite3"
    job = "rdr_tenant_contradiction"
    with _client(store_path) as (client, engine):
        refused = client.post(
            "/renders", json=_payload(job, custody_tenant=ALPHA), headers=_tenant(BETA)
        )

        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"]["code"] == "tenant_scope_contradiction"
        assert engine.calls == 0, "refusal must precede the render"
    with closing(sqlite3.connect(store_path)) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM render_job WHERE render_job_id = ?", (job,)
        ).fetchone()[0]
    assert count == 0, "refusal must precede the create"


def test_the_same_job_id_from_another_tenant_is_a_conflict_not_a_takeover(
    tmp_path: Path,
) -> None:
    """A cross-tenant collision on the raw key is the same conflict a same-tenant
    package mismatch is: one signal class, no new existence oracle, and the row keeps
    its owner."""

    store_path = tmp_path / "render-store.sqlite3"
    job = "rdr_tenant_collision"
    payload = _payload(job, custody_tenant=None)
    with _client(store_path) as (client, _):
        assert client.post("/renders", json=payload, headers=_tenant(ALPHA)).status_code == 201
        collided = client.post("/renders", json=payload, headers=_tenant(BETA))

        assert collided.status_code == 409, collided.text
        assert collided.json()["detail"]["code"] == "render_job_conflict"
        assert _row_tenant(store_path, job) == ALPHA
        # And the same-tenant replay is still the idempotent replay it always was.
        assert client.post("/renders", json=payload, headers=_tenant(ALPHA)).status_code == 200


def test_a_job_created_without_a_tenant_stays_readable_and_unattributed(
    tmp_path: Path,
) -> None:
    """Step (a): the producer is not sending the header yet. Its jobs are admitted,
    carry no tenant, remain readable with or without a header, and are never given an
    owner they did not assert."""

    store_path = tmp_path / "render-store.sqlite3"
    job = "rdr_tenant_unattributed"
    with _client(store_path) as (client, _):
        assert client.post("/renders", json=_payload(job, custody_tenant=None)).status_code == 201
        assert _row_tenant(store_path, job) is None
        assert client.get(f"/renders/{job}").status_code == 200
        assert client.get(f"/renders/{job}", headers=_tenant(ALPHA)).status_code == 200
        # A later replay WITH a header must not quietly adopt the row.
        replay = client.post(
            "/renders", json=_payload(job, custody_tenant=None), headers=_tenant(ALPHA)
        )
        assert replay.status_code == 200
        assert _row_tenant(store_path, job) is None


def test_custody_carries_the_admitted_tenant_never_the_body_claim(tmp_path: Path) -> None:
    """The header Archive receives is the tenant the job was admitted under. The body's
    custody block supplies it only for a job no tenant was admitted for."""

    store_path = tmp_path / "render-store.sqlite3"
    transport = _RecordingTransport()
    service, _ = _service(store_path, transport=transport)

    def package(job: str, custody_tenant: str | None) -> RenderPackage:
        return RenderPackage.model_validate(_payload(job, custody_tenant=custody_tenant))

    service.submit(package("rdr_custody_admitted", ALPHA), admitted_tenant=ALPHA)
    service.submit(package("rdr_custody_header_only", None), admitted_tenant="tenant-gamma")
    service.submit(package("rdr_custody_body_only", ALPHA), admitted_tenant=None)

    assert [headers["X-Tenant-Id"] for headers in transport.headers] == [
        ALPHA,
        "tenant-gamma",
        ALPHA,
    ]
    assert _row_tenant(store_path, "rdr_custody_header_only") == "tenant-gamma"


def test_tenant_scoping_survives_a_restart(tmp_path: Path) -> None:
    """Ownership is durable, not per-process: a fresh app over the same store still
    hides the job from the other tenant."""

    store_path = tmp_path / "render-store.sqlite3"
    job = "rdr_tenant_restart"
    with _client(store_path) as (client, _):
        created = client.post(
            "/renders", json=_payload(job, custody_tenant=ALPHA), headers=_tenant(ALPHA)
        )
        assert created.status_code == 201

    with _client(store_path) as (restarted, _):
        assert restarted.get(f"/renders/{job}", headers=_tenant(ALPHA)).status_code == 200
        assert restarted.get(f"/renders/{job}", headers=_tenant(BETA)).status_code == 404


def test_the_store_refuses_a_foreign_tenant_and_a_cross_tenant_create(tmp_path: Path) -> None:
    """The scope lives in the store's SQL, not only in the route: a foreign read is
    not-found and a cross-tenant create is a conflict at the durable boundary."""

    store = RenderStore(tmp_path / "render-store.sqlite3")
    arguments: dict[str, Any] = dict(
        render_job_id="rdr_store_scope",
        report_job_id="rjob_store",
        render_package_version="render_package.v1",
        package_hash="hash-store",
        report_type="portfolio_review",
        template_id="portfolio-review",
        template_version="v1",
        output_format="pdf",
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
    )
    store.create_or_get(**arguments, tenant_id=ALPHA)

    assert store.get("rdr_store_scope", tenant_id=ALPHA).tenant_id == ALPHA
    try:
        store.get("rdr_store_scope", tenant_id=BETA)
    except RenderJobNotFoundError:
        pass
    else:
        raise AssertionError("a foreign tenant read the job")
    try:
        store.create_or_get(**arguments, tenant_id=BETA)
    except RenderJobConflictError:
        pass
    else:
        raise AssertionError("a foreign tenant re-created the job")


def test_a_pre_admission_database_upgrades_to_unattributed_rows(tmp_path: Path) -> None:
    """Rows written before the tenant column existed surface with no tenant, stay
    readable to any admitted tenant while the header is optional, and are not
    backfilled -- the platform's stateful-migration bar: no state the new runtime
    neither reads nor recovers."""

    db_path = tmp_path / "render-store.sqlite3"
    with closing(sqlite3.connect(db_path)) as connection, connection:
        for version, migration in _MIGRATIONS:
            if version > 6:
                break
            migration(connection)
        connection.execute("PRAGMA user_version = 6")
        connection.execute(
            """
            INSERT INTO render_job (
                render_job_id, report_job_id, render_package_version, package_hash,
                report_type, template_id, template_version, output_format, status,
                runtime_engine, runtime_engine_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'rendered', 'typst', '0.14.2', ?, ?)
            """,
            (
                "rdr_legacy_no_tenant",
                "rjob_legacy",
                "render_package.v1",
                "hash-legacy",
                "portfolio_review",
                "portfolio-review",
                "v1",
                "pdf",
                "2026-07-05T00:00:00Z",
                "2026-07-05T00:00:00Z",
            ),
        )

    store = RenderStore(db_path)
    store.check_ready()

    assert store.get("rdr_legacy_no_tenant", tenant_id=None).tenant_id is None
    assert store.get("rdr_legacy_no_tenant", tenant_id=ALPHA).tenant_id is None
    assert store.get("rdr_legacy_no_tenant", tenant_id=BETA).tenant_id is None
