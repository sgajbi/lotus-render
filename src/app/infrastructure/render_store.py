from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Literal, cast

from app.contracts.renders import RenderFailureCategory, RenderJobStatus
from app.domain.rendering.models import RenderResult
from app.infrastructure.migrations.render_store import (
    CURRENT_RENDER_STORE_SCHEMA_VERSION,
    apply_render_store_migrations,
    render_store_columns,
)
from app.infrastructure.render_store_rows import (
    REQUIRED_RENDER_JOB_COLUMNS,
    StoredRenderJob,
    dt_from_text,
    dt_to_text,
    row_to_job,
    utc_now,
)


class RenderJobNotFoundError(ValueError):
    pass


class RenderJobConflictError(ValueError):
    pass


class RenderJobTransitionError(RuntimeError):
    pass


InFlightRenderJobStatus = Literal["accepted", "rendering"]


@dataclass(slots=True)
class CreateOrGetRenderJobResult:
    job: StoredRenderJob
    created: bool


@dataclass(frozen=True, slots=True)
class InFlightRenderJobSummary:
    status: InFlightRenderJobStatus
    count: int
    stale_count: int
    oldest_age_seconds: int | None
    stale_threshold_seconds: int


class RenderStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self.ensure_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            apply_render_store_migrations(connection)

    def check_ready(self) -> None:
        with self._connect() as connection:
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            row = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'render_job'
                """
            ).fetchone()
            columns = render_store_columns(connection)
        if row is None:
            raise RuntimeError("render_store_schema_missing:render_job")
        if schema_version < CURRENT_RENDER_STORE_SCHEMA_VERSION:
            raise RuntimeError("render_store_schema_version_outdated")
        missing_columns = REQUIRED_RENDER_JOB_COLUMNS - columns
        if missing_columns:
            raise RuntimeError(f"render_store_schema_missing:{sorted(missing_columns)[0]}")

    def get(self, render_job_id: str, *, tenant_id: str | None) -> StoredRenderJob:
        """The job as the admitted tenant may see it.

        With an admitted tenant the read is scoped: a job another tenant created is
        indistinguishable from one that does not exist. A job with no tenant of its
        own (created before admission existed) has no attributable owner and is
        excluded from tenant-scoped reads. The unscoped branch is for internal
        migration/recovery code, never the admitted HTTP boundary (C6-REN-02).
        """
        with self._connect() as connection:
            if tenant_id is None:
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM render_job
                    WHERE render_job_id = ? AND tenant_id = ?
                    """,
                    (render_job_id, tenant_id),
                ).fetchone()
        if row is None:
            raise RenderJobNotFoundError("render_job_not_found")
        return row_to_job(row)

    def in_flight_summaries(
        self,
        *,
        accepted_stale_seconds: int,
        rendering_stale_seconds: int,
        now: datetime | None = None,
    ) -> tuple[InFlightRenderJobSummary, ...]:
        observed_at = now or utc_now()
        thresholds = {
            "accepted": accepted_stale_seconds,
            "rendering": rendering_stale_seconds,
        }
        counts: dict[RenderJobStatus, int] = {"accepted": 0, "rendering": 0}
        stale_counts: dict[RenderJobStatus, int] = {"accepted": 0, "rendering": 0}
        oldest_ages: dict[RenderJobStatus, int | None] = {"accepted": None, "rendering": None}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, updated_at
                FROM render_job
                WHERE status IN ('accepted', 'rendering')
                """
            ).fetchall()
        for row in rows:
            status = cast(InFlightRenderJobStatus, row["status"])
            updated_at = dt_from_text(row["updated_at"]) or observed_at
            age_seconds = _age_seconds(updated_at, observed_at)
            counts[status] += 1
            if age_seconds >= thresholds[status]:
                stale_counts[status] += 1
            current_oldest = oldest_ages[status]
            if current_oldest is None or age_seconds > current_oldest:
                oldest_ages[status] = age_seconds
        return (
            InFlightRenderJobSummary(
                status="accepted",
                count=counts["accepted"],
                stale_count=stale_counts["accepted"],
                oldest_age_seconds=oldest_ages["accepted"],
                stale_threshold_seconds=accepted_stale_seconds,
            ),
            InFlightRenderJobSummary(
                status="rendering",
                count=counts["rendering"],
                stale_count=stale_counts["rendering"],
                oldest_age_seconds=oldest_ages["rendering"],
                stale_threshold_seconds=rendering_stale_seconds,
            ),
        )

    def create_or_get(self, **kwargs: Any) -> StoredRenderJob:
        return self.create_or_get_with_outcome(**kwargs).job

    def create_or_get_with_outcome(
        self,
        *,
        render_job_id: str,
        report_job_id: str,
        render_package_version: str,
        package_hash: str,
        snapshot_id: str = "",
        lineage_refs: tuple[str, ...] = (),
        disclosure_refs: tuple[str, ...] = (),
        requested_by: str = "",
        package_correlation_id: str = "",
        package_trace_id: str = "",
        report_type: str,
        template_id: str,
        template_version: str,
        output_format: str,
        runtime_engine: str,
        runtime_engine_version: str,
        tenant_id: str | None,
    ) -> CreateOrGetRenderJobResult:
        """Create the job under the admitted tenant, or return the existing one.

        The tenant is the admitted transport context, never a body claim. An existing
        job owned by a different tenant is a cross-tenant collision on the raw key and
        surfaces as the same conflict a same-tenant package mismatch does -- one
        signal class, no new existence oracle. An existing job with no tenant stays
        unattributed: the caller's assertion at the boundary is not proof of
        ownership, so it is never backfilled (C6-REN-02).
        """
        with self._lock:
            with self._connect() as connection:
                now = utc_now()
                now_text = dt_to_text(now)
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO render_job (
                        render_job_id, report_job_id, render_package_version, package_hash,
                        snapshot_id, lineage_refs_json, disclosure_refs_json, requested_by,
                        package_correlation_id, package_trace_id, report_type, template_id,
                        template_version, output_format, status, failure_category,
                        failure_message, runtime_engine, runtime_engine_version,
                        determinism_mode, determinism_statement, bounded_determinism_fingerprint,
                        artifact_sha256, mime_type, output_size_bytes, render_duration_ms,
                        created_at, updated_at, completed_at, tenant_id
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        render_job_id,
                        report_job_id,
                        render_package_version,
                        package_hash,
                        snapshot_id,
                        json.dumps(list(lineage_refs), separators=(",", ":")),
                        json.dumps(list(disclosure_refs), separators=(",", ":")),
                        requested_by,
                        package_correlation_id,
                        package_trace_id,
                        report_type,
                        template_id,
                        template_version,
                        output_format,
                        "accepted",
                        None,
                        None,
                        runtime_engine,
                        runtime_engine_version,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        now_text,
                        now_text,
                        None,
                        tenant_id,
                    ),
                )
                created = cursor.rowcount == 1
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                assert row is not None
                job = row_to_job(row)
                if tenant_id is not None and job.tenant_id != tenant_id:
                    raise RenderJobConflictError("render_job_conflict")
                if job.package_hash != package_hash:
                    raise RenderJobConflictError("render_job_conflict")
                return CreateOrGetRenderJobResult(job=job, created=created)

    def claim_for_rendering(
        self,
        render_job_id: str,
        *,
        rendering_stale_seconds: int,
        now: datetime | None = None,
    ) -> StoredRenderJob | None:
        """Take exclusive ownership of a job so this caller may render it.

        A job sitting at ``accepted`` is always claimable: nobody is rendering it yet.
        A job at ``rendering`` is claimable only once it is stale, which means the worker
        that owned it died without reaching a terminal state -- before this, such a row
        stayed at ``rendering`` forever because resubmission short-circuited (issue #105).

        Returns ``None`` when the job is not claimable, which is the ordinary outcome for
        a concurrent duplicate submission of a render that is genuinely still running.
        The claim is a single conditional UPDATE, so exactly one caller can win it.

        Every won claim increments ``claim_generation`` in that same UPDATE. The
        generation is the claim's identity: terminal and custody writes are fenced to
        it, so an attempt whose job was taken over while it was stalled holds a stale
        generation and none of its writes can land (#313). A timestamp going stale
        proves nothing about whether the old process died -- the generation is what
        makes the takeover exclusive rather than merely probable.
        """
        observed_at = now or utc_now()
        stale_cutoff = dt_to_text(observed_at - timedelta(seconds=rendering_stale_seconds))
        with self._lock:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT status FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                if existing is None:
                    raise RenderJobNotFoundError("render_job_not_found")
                cursor = connection.execute(
                    """
                    UPDATE render_job
                    SET status = 'rendering', updated_at = ?,
                        claim_generation = claim_generation + 1
                    WHERE render_job_id = ?
                      AND (
                        status = 'accepted'
                        OR (status = 'rendering' AND updated_at <= ?)
                      )
                    """,
                    (dt_to_text(observed_at), render_job_id, stale_cutoff),
                )
                if cursor.rowcount != 1:
                    return None
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
        return row_to_job(row)

    def mark_rendered(
        self, render_job_id: str, result: RenderResult, *, claim_generation: int
    ) -> StoredRenderJob:
        return self._update(
            render_job_id=render_job_id,
            status="rendered",
            failure_category=None,
            failure_message=None,
            determinism_mode=result.diagnostic.determinism_mode,
            determinism_statement=result.diagnostic.determinism_statement,
            bounded_determinism_fingerprint=result.diagnostic.bounded_determinism_fingerprint,
            template_digest=result.diagnostic.template_digest,
            template_publication=result.diagnostic.template_publication,
            artifact_sha256=f"sha256:{result.diagnostic.artifact_sha256}",
            mime_type=result.diagnostic.mime_type,
            output_size_bytes=result.diagnostic.output_size_bytes,
            render_duration_ms=result.diagnostic.render_duration_ms,
            completed_at=utc_now(),
            expected_statuses=("rendering",),
            expected_claim_generation=claim_generation,
        )

    def mark_failed(
        self,
        *,
        render_job_id: str,
        failure_category: RenderFailureCategory,
        failure_message: str,
        claim_generation: int,
    ) -> StoredRenderJob:
        return self._update(
            render_job_id=render_job_id,
            status="failed",
            failure_category=failure_category,
            failure_message=failure_message,
            determinism_mode=None,
            determinism_statement=None,
            bounded_determinism_fingerprint=None,
            template_digest=None,
            artifact_sha256=None,
            mime_type=None,
            output_size_bytes=None,
            render_duration_ms=None,
            completed_at=utc_now(),
            template_publication=None,
            expected_statuses=("accepted", "rendering"),
            expected_claim_generation=claim_generation,
        )

    def record_archive_outcome(
        self,
        render_job_id: str,
        *,
        archive_state: str,
        archive_document_id: str | None,
        archive_request_id: str | None,
        archive_detail: str | None,
        expected_claim_generation: int,
    ) -> StoredRenderJob:
        """Record the custody truth for a rendered artifact without touching status.

        The render outcome and the archive outcome are different facts with different
        authorities: the job stays 'rendered' whatever Archive said (issue #120), so
        this write deliberately bypasses the status-transition machinery.

        It does not bypass ownership: the write is fenced to the claim generation the
        caller holds, so a stale attempt's custody cannot replace the winner's (#313).
        """
        with self._lock:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT claim_generation FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                if existing is None:
                    raise RenderJobNotFoundError("render_job_not_found")
                cursor = connection.execute(
                    """
                    UPDATE render_job
                    SET archive_state = ?,
                        archive_document_id = ?,
                        archive_request_id = ?,
                        archive_detail = ?,
                        updated_at = ?
                    WHERE render_job_id = ? AND claim_generation = ?
                    """,
                    (
                        archive_state,
                        archive_document_id,
                        archive_request_id,
                        archive_detail,
                        dt_to_text(utc_now()),
                        render_job_id,
                        expected_claim_generation,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RenderJobTransitionError(
                        "stale_archive_outcome_write:"
                        f"expected_generation_{expected_claim_generation}"
                        f"_found_{int(existing['claim_generation'])}"
                    )
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                return row_to_job(row)

    def _update(
        self,
        *,
        render_job_id: str,
        status: RenderJobStatus,
        failure_category: RenderFailureCategory | None,
        failure_message: str | None,
        determinism_mode: str | None,
        determinism_statement: str | None,
        bounded_determinism_fingerprint: str | None,
        template_digest: str | None,
        template_publication: str | None,
        artifact_sha256: str | None,
        mime_type: str | None,
        output_size_bytes: int | None,
        render_duration_ms: int | None,
        completed_at: datetime | None,
        expected_statuses: tuple[RenderJobStatus, ...],
        expected_claim_generation: int,
    ) -> StoredRenderJob:
        """One conditional terminal write: right prior status AND the caller's claim.

        The status precondition alone cannot fence a stale attempt, because a stale
        takeover leaves the status at 'rendering' -- exactly what the old attempt
        expects to find. The claim generation is what distinguishes the two attempts,
        so both predicates live in the same UPDATE (#313).
        """
        with self._lock:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT status, claim_generation FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                if existing is None:
                    raise RenderJobNotFoundError("render_job_not_found")
                now_text = dt_to_text(utc_now())
                completed_at_text = dt_to_text(completed_at) if completed_at else None
                placeholders = ",".join("?" for _ in expected_statuses)
                cursor = connection.execute(
                    """
                    UPDATE render_job
                    SET status = ?, failure_category = ?, failure_message = ?,
                        determinism_mode = ?, determinism_statement = ?,
                        bounded_determinism_fingerprint = ?, template_digest = ?,
                        template_publication = ?,
                        artifact_sha256 = ?, mime_type = ?,
                        output_size_bytes = ?, render_duration_ms = ?, updated_at = ?,
                        completed_at = ?
                    WHERE render_job_id = ? AND claim_generation = ? AND status IN (
                    """
                    + placeholders
                    + """
                    )
                    """,
                    (
                        status,
                        failure_category,
                        failure_message,
                        determinism_mode,
                        determinism_statement,
                        bounded_determinism_fingerprint,
                        template_digest or "",
                        template_publication,
                        artifact_sha256,
                        mime_type,
                        output_size_bytes,
                        render_duration_ms,
                        now_text,
                        completed_at_text,
                        render_job_id,
                        expected_claim_generation,
                        *expected_statuses,
                    ),
                )
                if cursor.rowcount != 1:
                    raise _transition_refusal(
                        existing,
                        status=status,
                        expected_statuses=expected_statuses,
                        expected_claim_generation=expected_claim_generation,
                    )
                row = connection.execute(
                    "SELECT * FROM render_job WHERE render_job_id = ?",
                    (render_job_id,),
                ).fetchone()
                assert row is not None
                return row_to_job(row)


def _transition_refusal(
    existing: sqlite3.Row,
    *,
    status: RenderJobStatus,
    expected_statuses: tuple[RenderJobStatus, ...],
    expected_claim_generation: int,
) -> RenderJobTransitionError:
    """Name why a terminal write did not land: wrong prior status, or a stale claim.

    A stale claim leaves the status exactly as the loser expects, so the two refusals
    are distinguishable only here -- the message tells an operator whether the job
    moved on (invalid transition) or was taken over (stale claim).
    """
    current_status = str(existing["status"])
    current_generation = int(existing["claim_generation"])
    if current_status in expected_statuses and current_generation != expected_claim_generation:
        return RenderJobTransitionError(
            "stale_render_claim:"
            f"expected_generation_{expected_claim_generation}"
            f"_found_{current_generation}"
        )
    return RenderJobTransitionError(f"invalid_render_job_transition:{current_status}->{status}")


def _age_seconds(updated_at: datetime, observed_at: datetime) -> int:
    elapsed = observed_at.astimezone(UTC) - updated_at.astimezone(UTC)
    return max(0, int(elapsed.total_seconds()))
