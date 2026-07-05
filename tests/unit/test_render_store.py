from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.domain.render_attempts.models import RenderAttempt
from app.domain.rendering.models import RenderDiagnostic, RenderResult
from app.infrastructure.render_store import (
    RenderJobConflictError,
    RenderJobNotFoundError,
    RenderJobTransitionError,
    RenderStore,
)


def _build_store(tmp_path: Path) -> RenderStore:
    return RenderStore(tmp_path / "render-store.sqlite3")


def test_render_store_check_ready_reports_missing_schema(tmp_path: Path) -> None:
    store = _build_store(tmp_path)

    with sqlite3.connect(tmp_path / "render-store.sqlite3") as connection:
        connection.execute("DROP TABLE render_job")
        connection.commit()

    with pytest.raises(RuntimeError, match="render_store_schema_missing:render_job"):
        store.check_ready()


def test_render_store_get_unknown_job_raises_not_found(tmp_path: Path) -> None:
    store = _build_store(tmp_path)

    with pytest.raises(RenderJobNotFoundError, match="render_job_not_found"):
        store.get("rdr_missing")


def test_render_store_mark_rendering_unknown_job_raises_not_found(tmp_path: Path) -> None:
    store = _build_store(tmp_path)

    with pytest.raises(RenderJobNotFoundError, match="render_job_not_found"):
        store.mark_rendering("rdr_missing")


def _create_job(store: RenderStore, render_job_id: str = "rdr_store") -> str:
    job = store.create_or_get(
        render_job_id=render_job_id,
        report_job_id="rjob_store",
        render_package_version="render_package.v1",
        package_hash="hash-a",
        report_type="portfolio_review",
        template_id="portfolio-review",
        template_version="v1",
        output_format="pdf",
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
    )
    return job.render_job_id


def _render_result(render_job_id: str) -> RenderResult:
    return RenderResult(
        attempt=RenderAttempt(
            render_job_id=render_job_id,
            report_job_id="rjob_store",
            attempt_number=1,
            template_id="portfolio-review",
            template_version="v1",
            output_format="pdf",
        ),
        diagnostic=RenderDiagnostic(
            render_job_id=render_job_id,
            render_package_version="render_package.v1",
            template_id="portfolio-review",
            template_version="v1",
            runtime_engine="typst",
            runtime_engine_version="0.14.2",
            output_format="pdf",
            status="rendered",
            determinism_mode="bounded_runtime_envelope",
            determinism_statement="bounded",
            bounded_determinism_fingerprint="fingerprint",
            artifact_sha256="artifact",
            mime_type="application/pdf",
            output_size_bytes=12,
            render_duration_ms=5,
        ),
        artifact_bytes=b"%PDF",
    )


def test_render_store_rejects_terminal_state_overwrites(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    render_job_id = _create_job(store)
    store.mark_rendering(render_job_id)
    store.mark_failed(
        render_job_id=render_job_id,
        failure_category="template_render_failed",
        failure_message="failed",
    )

    with pytest.raises(RenderJobTransitionError, match="failed->rendered"):
        store.mark_rendered(render_job_id, _render_result(render_job_id))

    with pytest.raises(RenderJobTransitionError, match="failed->rendering"):
        store.mark_rendering(render_job_id)


def test_render_store_rejects_rendered_state_overwrites(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    render_job_id = _create_job(store)
    store.mark_rendering(render_job_id)
    store.mark_rendered(render_job_id, _render_result(render_job_id))

    with pytest.raises(RenderJobTransitionError, match="rendered->failed"):
        store.mark_failed(
            render_job_id=render_job_id,
            failure_category="template_render_failed",
            failure_message="late failure",
        )


def test_render_store_create_or_get_is_atomic_across_store_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "render-store.sqlite3"
    RenderStore(db_path)

    def create_same_payload() -> str:
        store = RenderStore(db_path)
        return store.create_or_get(
            render_job_id="rdr_concurrent",
            report_job_id="rjob_concurrent",
            render_package_version="render_package.v1",
            package_hash="hash-same",
            report_type="portfolio_review",
            template_id="portfolio-review",
            template_version="v1",
            output_format="pdf",
            runtime_engine="typst",
            runtime_engine_version="0.14.2",
        ).status

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: create_same_payload(), range(16)))

    assert statuses == ["accepted"] * 16


def test_render_store_create_or_get_conflicts_for_different_package_hash(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "render-store.sqlite3"
    store = RenderStore(db_path)
    _create_job(store, "rdr_conflict")

    with pytest.raises(RenderJobConflictError, match="render_job_conflict"):
        store.create_or_get(
            render_job_id="rdr_conflict",
            report_job_id="rjob_store",
            render_package_version="render_package.v1",
            package_hash="hash-b",
            report_type="portfolio_review",
            template_id="portfolio-review",
            template_version="v1",
            output_format="pdf",
            runtime_engine="typst",
            runtime_engine_version="0.14.2",
        )
