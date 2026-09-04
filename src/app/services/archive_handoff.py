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

- **A timeout is ``archive_pending``, never a guess.** The request may have committed
  after the deadline; claiming failure invites a needless redelivery and claiming
  success certifies what was not observed. Reconciliation resolves it by request id,
  outside the render path -- which is also why the timeout is not retried inline:
  the caller is waiting on a synchronous submit, and the pending state already names
  the recovery.

- **A refusal is ``archive_failed`` with Archive's own words.** ``declared_checksum_
  mismatch`` names both digests; ``artifact_identity_collision`` names the custody
  conflict. Refusals are not retried: the same request would meet the same refusal.
  A refused connection is also failed -- nothing reached Archive, so redelivery is
  safe and reconciliation has nothing to find. 5xx and refused connections retry a
  bounded number of times; if a 5xx did commit before erroring, the idempotent
  replay converges on the committed record.

- **The render is never failed by the handoff.** The artifact is real whatever
  happens here; the job stays ``rendered`` and carries the archive truth alongside.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol

from app.contracts.render_package import RenderPackage
from app.domain.rendering.models import RenderResult
from app.infrastructure.render_store import StoredRenderJob
from app.observability.render_metrics import record_render_operation
from app.services.render_ports import RenderJobStorePort

logger = logging.getLogger(__name__)

ArchiveState = Literal["archived_verified", "archive_pending", "archive_failed"]

#: Statuses where the request is worth re-sending: the failure is Archive's moment,
#: not the request's content. Everything else in 4xx/5xx is terminal for this call.
_RETRYABLE_STATUSES = frozenset({502, 503, 504})

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
    return metadata


class ArchiveTransport(Protocol):
    def post_document(
        self, payload: Mapping[str, object], *, headers: Mapping[str, str]
    ) -> tuple[int, Mapping[str, object]]: ...


class StdlibArchiveTransport:
    """One bounded POST via the standard library.

    The handoff is a single request-response with an explicit deadline; adding a
    runtime HTTP dependency for that would be speculation. HTTP error statuses are
    responses, not exceptions; a deadline expiry surfaces as TimeoutError and a
    connection that never carried the request as OSError, because the caller treats
    those two futures differently (pending versus failed).
    """

    def __init__(self, base_url: str, *, timeout_seconds: float) -> None:
        normalized = base_url.rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError(f"archive_base_url_not_http:{base_url}")
        self._url = f"{normalized}/documents"
        self._timeout_seconds = timeout_seconds

    def post_document(
        self, payload: Mapping[str, object], *, headers: Mapping[str, str]
    ) -> tuple[int, Mapping[str, object]]:
        request = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return int(response.status), _parse_body(response.read())
        except urllib.error.HTTPError as error:
            return int(error.code), _parse_body(error.read())
        except TimeoutError:
            raise
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError(str(error.reason)) from error
            raise OSError(str(error.reason)) from error


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
        last_detail = "archive_unreachable"
        for attempt in range(1, self._max_attempts + 1):
            try:
                status, body = self._transport.post_document(payload, headers=headers)
            except TimeoutError:
                return ArchiveHandoffOutcome(
                    archive_state="archive_pending",
                    archive_request_id=archive_request_id,
                    archive_detail=(
                        "archive_timeout: no response within the deadline; "
                        "reconcile by archive_request_id"
                    ),
                )
            except OSError as error:
                last_detail = _bounded(f"archive_unreachable: {error}")
            else:
                settled = _settled_outcome(status, body, archive_request_id)
                if settled is not None:
                    return settled
                last_detail = _refusal_detail(status, body)
            if attempt < self._max_attempts:
                self._sleep(self._retry_backoff_seconds * attempt)
        return ArchiveHandoffOutcome(
            archive_state="archive_failed",
            archive_request_id=archive_request_id,
            archive_detail=last_detail,
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
    """The terminal outcome for one answer, or None when the answer is retryable."""
    if status in (200, 201):
        document_id = body.get("document_id")
        if isinstance(document_id, str) and document_id:
            return ArchiveHandoffOutcome(
                archive_state="archived_verified",
                archive_request_id=archive_request_id,
                archive_document_id=document_id,
            )
        # A success without a durable id proves nothing; custody is claimed only
        # on evidence (fail-closed).
        return ArchiveHandoffOutcome(
            archive_state="archive_failed",
            archive_request_id=archive_request_id,
            archive_detail="archive_response_missing_document_id",
        )
    if status in _RETRYABLE_STATUSES:
        return None
    return ArchiveHandoffOutcome(
        archive_state="archive_failed",
        archive_request_id=archive_request_id,
        archive_detail=_refusal_detail(status, body),
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
