"""The handoff speaks Archive's settled contract and reports only what it observed.

The counterpart semantics live in lotus-archive#118 and are mirrored here verbatim so
the fakes cannot drift from the real authority (the four lotus-ai P1s were all masked
by fakes that answered more politely than the adapter they stood in for): a refusal
arrives as Archive's error envelope with its own code; a success carries the durable
``document_id``; a replay of a committed request id converges on the committed record.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from app.contracts.examples import PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH
from app.contracts.render_package import RenderPackage
from app.services.archive_handoff import (
    ArchiveDeliveryNotSentError,
    ArchiveHandoff,
    ArchiveHandoffOutcome,
    ArchiveOutcomeUnknownError,
    build_archive_metadata,
    derive_archive_request_id,
)

#: The facts only Report knows, delivered inside the package as render_context.archive.
CUSTODY = {
    "report_request_id": "req_2026_09_04_0001",
    "portfolio_scope": '{"portfolio_ids":["PF-001"]}',
    "portfolio_id": "PF-001",
    "client_reference": "CL-778",
    "as_of_date": "2026-08-31",
    "reporting_period_start": "2026-01-01",
    "reporting_period_end": "2026-08-31",
    "frequency": "ad_hoc",
    "classification": "confidential",
    "region": "SG",
    "tenant_id": "tenant-alpha",
}

REFERENCE = "LOTUS-SG-PF-001-2026-08-31-PRV1-7F3A"
ARTIFACT = b"%PDF-1.7\n% governed artifact bytes"
ARTIFACT_SHA = hashlib.sha256(ARTIFACT).hexdigest()


def _package(render_context: dict[str, Any] | None = None) -> RenderPackage:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    if render_context is not None:
        payload["render_context"] = render_context
    return RenderPackage.model_validate(payload)


def _custody_context(**overrides: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "timezone": "Asia/Singapore",
        "document_reference": REFERENCE,
        "archive": dict(CUSTODY),
    }
    context.update(overrides)
    return context


def _metadata(package: RenderPackage, **overrides: Any) -> dict[str, object] | None:
    arguments: dict[str, Any] = {
        "artifact_sha256": ARTIFACT_SHA,
        "mime_type": "application/pdf",
        "render_service_version": "0.1.0",
        "runtime_engine": "typst",
        "runtime_engine_version": "0.14.2",
        "template_digest": "sha256:feedbeef",
    }
    arguments.update(overrides)
    return build_archive_metadata(package, **arguments)


class _ScriptedTransport:
    """Answers exactly like Archive's HTTP surface: envelopes, statuses, exceptions."""

    def __init__(self, *script: tuple[int, dict[str, Any]] | Exception) -> None:
        self._script = list(script)
        self.calls: list[tuple[dict[str, Any], dict[str, str]]] = []

    def post_document(self, payload: Any, *, headers: Any) -> tuple[int, dict[str, Any]]:
        self.calls.append((dict(payload), dict(headers)))
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _refusal_envelope(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": "corr-golden-portfolio-review-v1",
            "service": "lotus-archive",
        }
    }


def _handoff(transport: _ScriptedTransport, **overrides: Any) -> ArchiveHandoff:
    sleeps: list[float] = overrides.pop("sleeps", [])
    arguments: dict[str, Any] = {
        "render_service_version": "0.1.0",
        "max_attempts": 3,
        "retry_backoff_seconds": 0.05,
        "sleep": sleeps.append,
    }
    arguments.update(overrides)
    return ArchiveHandoff(transport, **arguments)


def _deliver(handoff: ArchiveHandoff, package: RenderPackage) -> ArchiveHandoffOutcome | None:
    return handoff.deliver(
        package,
        artifact_bytes=ARTIFACT,
        artifact_sha256=ARTIFACT_SHA,
        mime_type="application/pdf",
        runtime_engine="typst",
        runtime_engine_version="0.14.2",
        template_digest="sha256:feedbeef",
    )


# ---------------------------------------------------------------- identity


def test_the_request_id_is_a_pure_function_of_reference_and_bytes() -> None:
    """Redelivering the same bytes must converge on the same custody record, while a
    regenerated document must be a distinct one -- no stored state, no clock."""

    first = derive_archive_request_id(REFERENCE, ARTIFACT_SHA)
    assert first == derive_archive_request_id(REFERENCE, ARTIFACT_SHA)
    assert first != derive_archive_request_id(REFERENCE, hashlib.sha256(b"other").hexdigest())
    assert first != derive_archive_request_id("LOTUS-OTHER-REF", ARTIFACT_SHA)
    assert first.startswith("areq_")


def test_a_sha_prefix_is_normalized_not_a_different_identity() -> None:
    """Render stores 'sha256:<hex>' while the wire wants bare hex; the two spellings
    of one digest must never mint two custody records."""

    assert derive_archive_request_id(REFERENCE, f"sha256:{ARTIFACT_SHA}") == (
        derive_archive_request_id(REFERENCE, ARTIFACT_SHA)
    )


def test_render_owned_truths_overlay_the_custody_block() -> None:
    """Report's block passes through verbatim, but a block that tries to speak for
    Render (the declared digest, the producing service) loses -- and the whole dict is
    replay-stable, because Archive refuses a request id reused with different metadata."""

    custody = dict(
        CUSTODY,
        declared_artifact_sha256="0" * 64,
        created_by_service="lotus-imposter",
    )
    package = _package(_custody_context(archive=custody))

    metadata = _metadata(package)
    assert metadata is not None
    assert metadata["declared_artifact_sha256"] == ARTIFACT_SHA
    assert metadata["created_by_service"] == "lotus-render"
    assert metadata["tenant_id"] == "tenant-alpha"
    assert metadata["as_of_date"] == "2026-08-31"
    assert metadata["document_reference"] == REFERENCE
    assert metadata["render_attempt_id"] == (f"{package.render_job_id}:{ARTIFACT_SHA[:16]}")
    assert metadata == _metadata(package), "metadata must be a pure function of its inputs"


def test_an_unknown_template_digest_is_omitted_never_invented() -> None:
    package = _package(_custody_context())
    metadata = _metadata(package, template_digest=None)
    assert metadata is not None
    assert "template_digest" not in metadata


def test_no_custody_block_or_no_reference_means_no_handoff() -> None:
    """Packages that predate the cutover carry neither block; for them the handoff
    does not apply -- which is a different fact from a failed one."""

    assert _metadata(_package()) is None
    assert _metadata(_package({"timezone": "UTC", "document_reference": REFERENCE})) is None
    assert _metadata(_package({"archive": dict(CUSTODY)})) is None
    assert _metadata(_package(_custody_context(document_reference="   "))) is None

    transport = _ScriptedTransport()
    assert _deliver(_handoff(transport), _package()) is None
    assert transport.calls == [], "no handoff may reach the wire without an identity"


# ---------------------------------------------------------------- outcomes


def test_verified_custody_carries_the_durable_document_id() -> None:
    transport = _ScriptedTransport(
        (201, {"document_id": "doc_ab12", "archive_request_id": "ignored"})
    )

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome == ArchiveHandoffOutcome(
        archive_state="archived_verified",
        archive_request_id=derive_archive_request_id(REFERENCE, ARTIFACT_SHA),
        archive_document_id="doc_ab12",
    )


def test_a_timeout_is_pending_never_a_guess_and_never_hammered() -> None:
    """After the deadline the request MAY have committed. Claiming failure invites a
    needless redelivery; retrying inline doubles the time a waiting caller spends; the
    truthful state is pending, resolved by reconciliation on the derived request id."""

    transport = _ScriptedTransport(TimeoutError("timed out"))

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_pending"
    assert outcome.archive_request_id == derive_archive_request_id(REFERENCE, ARTIFACT_SHA)
    assert outcome.archive_detail is not None
    assert "reconcile" in outcome.archive_detail
    assert len(transport.calls) == 1


def test_a_named_refusal_carries_archives_own_words() -> None:
    """A declared-checksum mismatch names both digests (lotus-archive#118); the job
    must keep those words, and the same request must not be retried into the same wall."""

    message = (
        "declared sha256 aaaa... does not match computed sha256 bbbb... over the received bytes"
    )
    transport = _ScriptedTransport((422, _refusal_envelope("declared_checksum_mismatch", message)))

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_failed"
    assert outcome.archive_document_id is None
    assert outcome.archive_detail is not None
    assert "archive_refused_422" in outcome.archive_detail
    assert "declared_checksum_mismatch" in outcome.archive_detail
    assert message in outcome.archive_detail
    assert len(transport.calls) == 1


def test_an_identity_collision_is_a_terminal_refusal() -> None:
    transport = _ScriptedTransport(
        (
            409,
            _refusal_envelope(
                "artifact_identity_collision",
                "the same bytes are already in custody under a different document_reference",
            ),
        )
    )

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_failed"
    assert "artifact_identity_collision" in (outcome.archive_detail or "")
    assert len(transport.calls) == 1


def test_a_delivery_proven_never_sent_retries_then_fails_with_bounded_backoff() -> None:
    """The one transport failure allowed to say archive_failed: the connect itself
    failed, so the request provably never left this process -- redelivery is safe
    and reconciliation has nothing to find. After the configured attempts, not one."""

    sleeps: list[float] = []
    transport = _ScriptedTransport(
        ArchiveDeliveryNotSentError("connection refused"),
        ArchiveDeliveryNotSentError("connection refused"),
        ArchiveDeliveryNotSentError("connection refused"),
    )

    outcome = _deliver(_handoff(transport, sleeps=sleeps), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_failed"
    assert "archive_unreachable" in (outcome.archive_detail or "")
    assert len(transport.calls) == 3
    assert sleeps == [0.05, 0.10]


def test_a_connection_lost_after_the_request_was_accepted_is_pending() -> None:
    """The first byte left the process, so absence at Archive is no longer provable:
    a reset here may sit on top of a committed document, and claiming failure would
    invite a needless (though convergent) redelivery instead of a lookup."""

    transport = _ScriptedTransport(ArchiveOutcomeUnknownError("connection reset by peer"))

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_pending"
    assert outcome.archive_request_id == derive_archive_request_id(REFERENCE, ARTIFACT_SHA)
    assert outcome.archive_detail is not None
    assert "archive_outcome_unknown" in outcome.archive_detail
    assert "reconcile by archive_request_id" in outcome.archive_detail
    assert len(transport.calls) == 1


def test_a_server_commit_with_response_loss_never_mints_a_fresh_document() -> None:
    """The steering invariant, end to end: Archive commits, the response is lost,
    Render records pending -- and the later redelivery of the same bytes converges on
    the COMMITTED record because the request id is derived, not regenerated."""

    committed_id = "doc_committed_before_loss"

    class _CommitThenLoseTransport:
        def __init__(self) -> None:
            self.store: dict[str, str] = {}
            self.calls = 0

        def post_document(self, payload: Any, *, headers: Any) -> tuple[int, dict[str, Any]]:
            self.calls += 1
            request_id = str(payload["metadata"]["archive_request_id"])
            if request_id not in self.store:
                self.store[request_id] = committed_id
                raise ArchiveOutcomeUnknownError("response lost after commit")
            return (200, {"document_id": self.store[request_id]})

    transport = _CommitThenLoseTransport()
    handoff = ArchiveHandoff(
        transport,
        render_service_version="0.1.0",
        max_attempts=3,
        retry_backoff_seconds=0,
        sleep=lambda _: None,
    )

    first = _deliver(handoff, _package(_custody_context()))
    assert first is not None
    assert first.archive_state == "archive_pending", "a possible commit must never claim failure"
    assert first.archive_request_id is not None

    replay = _deliver(handoff, _package(_custody_context()))
    assert replay is not None
    assert replay.archive_state == "archived_verified"
    assert replay.archive_document_id == committed_id, "redelivery must find the committed record"
    assert len(transport.store) == 1, "no second governed document may exist"


def test_an_exhausted_5xx_sequence_is_pending_not_failed() -> None:
    """Every 503 was an ANSWER: something received the request, and any attempt may
    have committed before erroring. Exhaustion proves unavailability, not absence --
    the truthful state is pending, resolved by request id, never a fresh delivery."""

    sleeps: list[float] = []
    transport = _ScriptedTransport(
        (503, _refusal_envelope("internal_error", "restarting")),
        (503, _refusal_envelope("internal_error", "restarting")),
        (503, _refusal_envelope("internal_error", "restarting")),
    )

    outcome = _deliver(_handoff(transport, sleeps=sleeps), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_pending"
    assert outcome.archive_detail is not None
    assert "archive_refused_503" in outcome.archive_detail
    assert "reconcile by archive_request_id" in outcome.archive_detail
    assert len(transport.calls) == 3


def test_an_unclassifiable_transport_error_chooses_pending() -> None:
    """A transport that cannot prove which phase failed must not let the mapping
    claim definite absence: a bare OSError is treated as sent-but-unobserved."""

    transport = _ScriptedTransport(OSError("something happened"))

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_pending"
    assert "archive_outcome_unknown" in (outcome.archive_detail or "")
    assert len(transport.calls) == 1


def test_a_5xx_retry_converges_on_the_idempotent_replay() -> None:
    """If the failed attempt did commit before erroring, Archive's replay semantics
    return the committed record -- the retry is safe BECAUSE the request id is derived."""

    transport = _ScriptedTransport(
        (503, _refusal_envelope("internal_error", "restarting")),
        (200, {"document_id": "doc_ab12"}),
    )

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archived_verified"
    assert outcome.archive_document_id == "doc_ab12"
    assert len(transport.calls) == 2
    first_payload, second_payload = transport.calls[0][0], transport.calls[1][0]
    assert first_payload == second_payload, "a retry must be byte-for-byte the same request"


def test_a_success_naming_no_record_is_pending_not_assumed() -> None:
    """A 2xx that names no durable record is a LIKELY commit whose evidence went
    missing: claiming verified would certify what was not observed, and claiming
    failed would assert an absence the answer itself contradicts. Reconcile it."""

    transport = _ScriptedTransport((201, {}))

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_pending"
    assert outcome.archive_detail == (
        "archive_response_missing_document_id; reconcile by archive_request_id"
    )


# ---------------------------------------------------------------- the wire


def test_the_payload_carries_the_exact_bytes_and_the_caller_headers() -> None:
    """The whole point of the cutover: the bytes Archive verifies are the bytes Render
    produced, one hop, with the caller identity and tenant scope Archive authorizes on."""

    transport = _ScriptedTransport((201, {"document_id": "doc_ab12"}))
    package = _package(_custody_context())

    _deliver(_handoff(transport), package)

    payload, headers = transport.calls[0]
    assert base64.b64decode(payload["content_base64"]) == ARTIFACT
    metadata = payload["metadata"]
    assert metadata["declared_artifact_sha256"] == ARTIFACT_SHA
    assert headers["X-Caller-Service"] == "lotus-render"
    assert headers["X-Actor-Type"] == "service"
    assert headers["X-Actor-Id"] == package.requested_by
    assert headers["X-Tenant-Id"] == "tenant-alpha"
    assert headers["X-Region"] == "SG"
    assert headers["X-Correlation-ID"] == package.correlation_id
    assert headers["X-Trace-ID"] == package.trace_id


def test_a_refusal_with_no_envelope_still_names_the_status() -> None:
    """A proxy or crash page answers with no error body; the job must still say
    which status refused rather than an empty detail."""

    transport = _ScriptedTransport((400, {}))

    outcome = _deliver(_handoff(transport), _package(_custody_context()))

    assert outcome is not None
    assert outcome.archive_state == "archive_failed"
    assert outcome.archive_detail == "archive_refused_400"
