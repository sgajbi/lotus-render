"""Hand the exact rendered bytes to Archive's one custody authority (issue #120).

This is Render's leg of the evidence-chain cutover that retires lotus-report's byte
relay: the service that PRODUCED the bytes declares their identity and delivers them
itself, so the declared SHA-256 crosses exactly one hop and Archive independently
verifies it against what actually arrived (lotus-archive#118). There is deliberately
no second ingestion path -- this posts to the same ``POST /documents`` every archive
caller uses, with the same headers and the same metadata contract.

The cutover's decisions, as they land here:

- **Artifact identity is idempotent.** The archive request id is derived from
  ``(document_reference, artifact_sha256)``, so redelivering byte-identical output
  converges on the same custody record while a regenerated document (new bytes) is a
  distinct record by construction. Every other metadata field is likewise a pure
  function of the package, the bytes, or configuration -- never the attempt counter
  or the clock -- because Archive refuses a request id reused with different
  metadata, and a replay that cannot reproduce its own metadata would convert
  idempotency into a 409.

- **An unproven commit is ``archive_pending``, never a guess.** Only two futures may
  end as ``archive_failed``: a deterministic refusal (4xx -- Archive judged the
  content and the same request meets the same wall) and a delivery PROVEN never
  sent (the connect itself failed -- redelivery is safe and reconciliation has
  nothing to find). Everything else -- a deadline expiry, a connection lost after
  the first byte, a 5xx answer, a success that names no record, an error the
  transport cannot classify -- leaves the commit state unproven, and claiming
  definite absence there could mint a duplicate governed document. The truthful
  state for an unproven commit is pending: Archive resolves it by request id, and
  an extra lookup is always cheaper than a duplicate. This is why the transport
  keeps delivery phases distinct instead of collapsing them into one error.

- **A refusal is ``archive_failed`` with Archive's own words.** ``declared_checksum_
  mismatch`` names both digests; ``artifact_identity_collision`` names the custody
  conflict. Refusals are not retried: the same request would meet the same refusal.
  5xx answers and never-sent deliveries retry a bounded number of times; if a 5xx
  did commit before erroring, the idempotent replay converges on the committed
  record.

- **The render is never failed by the handoff.** The artifact is real whatever
  happens here; the job stays ``rendered`` and carries the archive truth alongside.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import logging
import time
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol

from app.contracts.render_package import RenderPackage
from app.domain.rendering.models import RenderResult
from app.infrastructure.render_store_rows import StoredRenderJob
from app.observability.render_metrics import record_render_operation
from app.services.render_ports import RenderJobStorePort

logger = logging.getLogger(__name__)

ArchiveState = Literal["archived_verified", "archive_pending", "archive_failed"]

#: How much of Archive's refusal is kept on the job. Enough to name the code and both
#: digests of a checksum mismatch; not an unbounded echo of an arbitrary error body.
_DETAIL_LIMIT = 500


@dataclass(frozen=True, slots=True)
class ArchiveHandoffOutcome:
    archive_state: ArchiveState
    archive_request_id: str | None
    archive_document_id: str | None = None
    archive_detail: str | None = None


def normalize_sha256(value: str) -> str:
    return value.strip().lower().removeprefix("sha256:")


def derive_archive_request_id(document_reference: str, artifact_sha256: str) -> str:
    """One custody request per (financial question, exact bytes) -- nothing else.

    Derived rather than generated so that redelivery needs no stored state: any
    holder of the same reference and the same bytes computes the same id, and
    Archive's idempotent replay does the converging.
    """
    digest = hashlib.sha256(
        f"{document_reference}\n{normalize_sha256(artifact_sha256)}".encode()
    ).hexdigest()
    return f"areq_{digest[:32]}"


def build_archive_metadata(
    render_package: RenderPackage,
    *,
    artifact_sha256: str,
    mime_type: str,
    render_service_version: str,
    runtime_engine: str,
    runtime_engine_version: str,
    template_digest: str | None,
    template_publication: str | None,
) -> dict[str, object] | None:
    """Custody metadata for the exact bytes, or None when no handoff applies.

    The package's ``render_context.archive`` block carries the facts only Report
    knows (tenant, region, portfolio scope, reporting period, classification,
    retention); they pass through verbatim. The fields Render is the authority on --
    identity, provenance, and the declared digest -- are overlaid last, so a custody
    block can never override what Render actually did.
    """
    custody = render_package.render_context.get("archive")
    reference = render_package.render_context.get("document_reference")
    if not isinstance(custody, Mapping) or not isinstance(reference, str) or not reference.strip():
        return None
    document_reference = reference.strip()
    declared_sha256 = normalize_sha256(artifact_sha256)
    metadata: dict[str, object] = dict(custody)
    metadata.update(
        {
            "archive_request_id": derive_archive_request_id(document_reference, declared_sha256),
            "document_reference": document_reference,
            "declared_artifact_sha256": declared_sha256,
            "report_job_id": render_package.report_job_id,
            "snapshot_id": render_package.snapshot_id,
            "render_job_id": render_package.render_job_id,
            # Derived from the bytes rather than the in-process attempt counter:
            # under bounded determinism, attempts that produced identical bytes are
            # the same evidence, and a replay must reproduce this field exactly.
            "render_attempt_id": f"{render_package.render_job_id}:{declared_sha256[:16]}",
            "report_type": render_package.report_type,
            "template_id": render_package.template_id,
            "template_version": render_package.template_version,
            "render_service_version": render_service_version,
            "report_data_contract_version": render_package.report_data_contract_version,
            "mime_type": mime_type,
            "output_format": render_package.output_format,
            "render_runtime_engine": runtime_engine,
            "render_runtime_engine_version": runtime_engine_version,
            "created_by_service": "lotus-render",
            "created_by_actor": render_package.requested_by,
        }
    )
    if template_digest:
        metadata["template_digest"] = template_digest
    if template_publication:
        metadata["template_publication"] = template_publication
    return metadata


class ArchiveDeliveryNotSentError(Exception):
    """Proven: the request never left this process (the connect itself failed)."""


class ArchiveOutcomeUnknownError(Exception):
    """The request may have reached Archive; its outcome was not observed."""


class ArchiveTransport(Protocol):
    def post_document(
        self, payload: Mapping[str, object], *, headers: Mapping[str, str]
    ) -> tuple[int, Mapping[str, object]]:
        """Return Archive's answer, or raise a delivery-phase-typed exception.

        HTTP statuses are answers, not exceptions. A transport that cannot prove
        which phase failed must raise ArchiveOutcomeUnknownError -- never a claim
        of definite absence.
        """
        ...


class StdlibArchiveTransport:
    """One bounded POST via the standard library, with delivery phases kept distinct.

    The handoff is a single request-response with an explicit deadline; adding a
    runtime HTTP dependency for that would be speculation. What the stdlib IS asked
    for is epistemic precision: an error while CONNECTING proves the request never
    left this process, while any error after the first byte was written may have
    left a committed document behind. urllib collapses those phases into one error,
    so this speaks http.client directly and types the two futures apart.
    """

    def __init__(self, base_url: str, *, timeout_seconds: float) -> None:
        parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError(f"archive_base_url_not_http:{base_url}")
        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port
        self._path = f"{parsed.path}/documents"
        self._timeout_seconds = timeout_seconds

    def post_document(
        self, payload: Mapping[str, object], *, headers: Mapping[str, str]
    ) -> tuple[int, Mapping[str, object]]:
        connection_class = (
            http.client.HTTPSConnection if self._scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_class(self._host, self._port, timeout=self._timeout_seconds)
        try:
            try:
                connection.connect()
            except OSError as error:
                raise ArchiveDeliveryNotSentError(str(error) or type(error).__name__) from error
            # From here on, bytes may have left the process: absence of the request
            # at Archive is no longer provable from this side of the wire.
            try:
                connection.request(
                    "POST",
                    self._path,
                    body=json.dumps(payload).encode("utf-8"),
                    headers=dict(headers),
                )
                response = connection.getresponse()
                return int(response.status), _parse_body(response.read())
            except (OSError, http.client.HTTPException) as error:
                raise ArchiveOutcomeUnknownError(str(error) or type(error).__name__) from error
        finally:
            connection.close()


def _parse_body(raw: bytes) -> Mapping[str, object]:
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return body if isinstance(body, Mapping) else {}


class ArchiveHandoff:
    """Deliver one rendered artifact into Archive custody and report the truth."""

    def __init__(
        self,
        transport: ArchiveTransport,
        *,
        render_service_version: str,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._transport = transport
        self._render_service_version = render_service_version
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep

    def deliver(
        self,
        render_package: RenderPackage,
        *,
        artifact_bytes: bytes,
        artifact_sha256: str,
        mime_type: str,
        runtime_engine: str,
        runtime_engine_version: str,
        template_digest: str | None,
        template_publication: str | None,
    ) -> ArchiveHandoffOutcome | None:
        """The custody outcome for these exact bytes, or None when no handoff applies."""
        metadata = build_archive_metadata(
            render_package,
            artifact_sha256=artifact_sha256,
            mime_type=mime_type,
            render_service_version=self._render_service_version,
            runtime_engine=runtime_engine,
            runtime_engine_version=runtime_engine_version,
            template_digest=template_digest,
            template_publication=template_publication,
        )
        if metadata is None:
            return None
        payload = {
            "metadata": metadata,
            "content_base64": base64.b64encode(artifact_bytes).decode("ascii"),
        }
        return self._post_until_settled(
            payload,
            headers=self._headers(render_package, metadata),
            archive_request_id=str(metadata["archive_request_id"]),
        )

    def _headers(
        self, render_package: RenderPackage, metadata: Mapping[str, object]
    ) -> dict[str, str]:
        # Tenant and region come from the custody block Report supplied; when they are
        # absent the handoff still posts and Archive's own authorization refuses it --
        # a named refusal on the job beats silently skipping custody.
        return {
            "Content-Type": "application/json",
            "X-Caller-Service": "lotus-render",
            "X-Caller-Application": "lotus-render",
            "X-Actor-Type": "service",
            "X-Actor-Id": render_package.requested_by,
            "X-Tenant-Id": str(metadata.get("tenant_id", "")),
            "X-Region": str(metadata.get("region", "")),
            "X-Correlation-ID": render_package.correlation_id,
            "X-Trace-ID": render_package.trace_id,
        }

    def _post_until_settled(
        self,
        payload: Mapping[str, object],
        *,
        headers: Mapping[str, str],
        archive_request_id: str,
    ) -> ArchiveHandoffOutcome:
        """Post until the outcome is settled, retrying only what is safe to retry.

        A proven-never-sent delivery retries and exhausts to archive_failed --
        genuinely retry-eligible, nothing to reconcile. A 5xx retries (replay under
        the derived id is safe) but exhausts to archive_pending, because an answer
        proves the request REACHED something and the commit state was never
        disproven. Every sent-but-unobserved future settles as pending immediately:
        the caller is waiting on a synchronous submit, and the pending state
        already names the recovery.
        """
        not_sent_detail = "archive_unreachable"
        last_answer_detail: str | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                status, body = self._transport.post_document(payload, headers=headers)
            except ArchiveDeliveryNotSentError as error:
                not_sent_detail = _bounded(f"archive_unreachable: {error}")
            except (TimeoutError, ArchiveOutcomeUnknownError, OSError) as error:
                # Sent-but-unobserved -- or an error the transport could not place
                # in a phase, which must be treated identically: never a claim of
                # definite absence.
                return _pending(archive_request_id, _unobserved_reason(error))
            else:
                settled = _settled_outcome(status, body, archive_request_id)
                if settled is not None:
                    return settled
                last_answer_detail = _refusal_detail(status, body)
            if attempt < self._max_attempts:
                self._sleep(self._retry_backoff_seconds * attempt)
        if last_answer_detail is not None:
            # At least one attempt was ANSWERED, so the request reached something
            # and any of those attempts may have committed: exhaustion proves
            # unavailability, never absence -- even if later attempts never sent.
            return _pending(archive_request_id, last_answer_detail)
        return ArchiveHandoffOutcome(
            archive_state="archive_failed",
            archive_request_id=archive_request_id,
            archive_detail=not_sent_detail,
        )


def hand_off_and_record(
    handoff: ArchiveHandoff | None,
    store: RenderJobStorePort,
    render_package: RenderPackage,
    result: RenderResult,
    stored: StoredRenderJob,
) -> StoredRenderJob:
    """Deliver the exact bytes into Archive custody; never fail the render doing it.

    The artifact is real whatever happens here -- the job stays 'rendered' and the
    response still carries the bytes. What the handoff adds is the custody truth on
    the job: verified, pending reconciliation, or a named refusal (issue #120).
    Recording that truth is itself best-effort for the same reason. A None handoff
    means this deployment has no Archive, and the job's null archive state stands.
    """
    if handoff is None:
        return stored
    started = perf_counter()
    diagnostic = result.diagnostic
    try:
        outcome = handoff.deliver(
            render_package,
            artifact_bytes=result.artifact_bytes,
            artifact_sha256=diagnostic.artifact_sha256 or "",
            mime_type=diagnostic.mime_type or "application/pdf",
            runtime_engine=diagnostic.runtime_engine,
            runtime_engine_version=diagnostic.runtime_engine_version,
            template_digest=diagnostic.template_digest,
            template_publication=diagnostic.template_publication,
        )
    except Exception:
        logger.exception("archive_handoff_unexpected_error")
        outcome = ArchiveHandoffOutcome(
            archive_state="archive_failed",
            archive_request_id=None,
            archive_detail="archive_handoff_unexpected_error",
        )
    if outcome is None:
        return stored
    record_render_operation(
        operation="archive_handoff",
        status=outcome.archive_state,
        duration_seconds=perf_counter() - started,
    )
    try:
        return store.record_archive_outcome(
            stored.render_job_id,
            archive_state=outcome.archive_state,
            archive_document_id=outcome.archive_document_id,
            archive_request_id=outcome.archive_request_id,
            archive_detail=outcome.archive_detail,
        )
    except Exception:
        logger.exception("archive_outcome_not_recorded")
        return stored


def _settled_outcome(
    status: int, body: Mapping[str, object], archive_request_id: str
) -> ArchiveHandoffOutcome | None:
    """The settled outcome for one answer, or None when another attempt is safe.

    Only a deterministic refusal (4xx) may say archive_failed: the answer proves
    Archive judged the request's content, and the same request meets the same wall.
    Any other non-success answer proves only that SOMETHING received the request --
    the commit state stays unproven, so the caller retries (safe under the derived
    request id) and exhaustion settles as pending upstream.
    """
    if status in (200, 201):
        document_id = body.get("document_id")
        if isinstance(document_id, str) and document_id:
            return ArchiveHandoffOutcome(
                archive_state="archived_verified",
                archive_request_id=archive_request_id,
                archive_document_id=document_id,
            )
        # A success that names no durable record: the commit is likely but
        # unproven, and claiming either way would be a guess -- reconcile it.
        return _pending(archive_request_id, "archive_response_missing_document_id")
    if 400 <= status < 500:
        return ArchiveHandoffOutcome(
            archive_state="archive_failed",
            archive_request_id=archive_request_id,
            archive_detail=_refusal_detail(status, body),
        )
    return None


def _unobserved_reason(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return "archive_timeout: no response within the deadline"
    return f"archive_outcome_unknown: {error}"


def _pending(archive_request_id: str, reason: str) -> ArchiveHandoffOutcome:
    return ArchiveHandoffOutcome(
        archive_state="archive_pending",
        archive_request_id=archive_request_id,
        archive_detail=_bounded(f"{reason}; reconcile by archive_request_id"),
    )


def _refusal_detail(status: int, body: Mapping[str, object]) -> str:
    """Archive's refusal in Archive's own words, bounded, never re-interpreted."""
    error = body.get("error")
    source = error if isinstance(error, Mapping) else body
    code = source.get("code")
    message = source.get("message")
    parts = [f"archive_refused_{status}"]
    if isinstance(code, str) and code:
        parts.append(code)
    if isinstance(message, str) and message:
        parts.append(message)
    return _bounded(": ".join(parts))


def _bounded(detail: str) -> str:
    return detail[:_DETAIL_LIMIT]
