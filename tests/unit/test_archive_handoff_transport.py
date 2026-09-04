"""The stdlib transport keeps delivery phases distinct; phases are the epistemics.

An error while CONNECTING proves the request never left this process -- the only
future allowed to become a definite "nothing to reconcile" failure. From the first
byte written, absence at Archive is no longer provable from this side of the wire,
so every later error must surface as an unknown outcome, never a claim of absence.
HTTP statuses, however ugly, are answers -- not exceptions.
"""

from __future__ import annotations

import http.client
import json
import socket
from collections.abc import Iterator
from typing import Any

import pytest

from app.services.archive_handoff import (
    ArchiveDeliveryNotSentError,
    ArchiveOutcomeUnknownError,
    StdlibArchiveTransport,
)

PAYLOAD = {"metadata": {"archive_request_id": "areq_x"}, "content_base64": "aGk="}
HEADERS = {"Content-Type": "application/json", "X-Caller-Service": "lotus-render"}


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body


class _FakeConnection:
    """Scripted stand-in for http.client's connection, one behaviour per phase."""

    script: dict[str, Any] = {}
    seen: dict[str, Any] = {}

    def __init__(self, host: str, port: int | None, timeout: float) -> None:
        _FakeConnection.seen.update(host=host, port=port, timeout=timeout)

    def connect(self) -> None:
        effect = self.script.get("connect")
        if isinstance(effect, Exception):
            raise effect

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        _FakeConnection.seen.update(method=method, path=path, body=body, headers=headers)
        effect = self.script.get("request")
        if isinstance(effect, Exception):
            raise effect

    def getresponse(self) -> _Response:
        effect = self.script.get("response")
        if isinstance(effect, Exception):
            raise effect
        assert isinstance(effect, _Response), "script must provide a response"
        return effect

    def close(self) -> None:
        _FakeConnection.seen["closed"] = True


@pytest.fixture(autouse=True)
def _fake_connection(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _FakeConnection.script = {}
    _FakeConnection.seen = {}
    monkeypatch.setattr(http.client, "HTTPConnection", _FakeConnection)
    monkeypatch.setattr(http.client, "HTTPSConnection", _FakeConnection)
    yield


def _transport(base_url: str = "http://archive.test:8150") -> StdlibArchiveTransport:
    return StdlibArchiveTransport(base_url, timeout_seconds=2.0)


def test_a_success_returns_the_parsed_body_over_the_exact_wire_shape() -> None:
    _FakeConnection.script = {
        "response": _Response(201, json.dumps({"document_id": "doc_1"}).encode())
    }

    status, body = _transport().post_document(PAYLOAD, headers=HEADERS)

    assert (status, body) == (201, {"document_id": "doc_1"})
    seen = _FakeConnection.seen
    assert (seen["host"], seen["port"], seen["timeout"]) == ("archive.test", 8150, 2.0)
    assert (seen["method"], seen["path"]) == ("POST", "/documents")
    assert json.loads(seen["body"].decode()) == PAYLOAD
    assert seen["closed"] is True


def test_a_base_path_prefix_is_preserved() -> None:
    _FakeConnection.script = {"response": _Response(201, b"{}")}
    _transport("http://archive.test:8150/api").post_document(PAYLOAD, headers=HEADERS)
    assert _FakeConnection.seen["path"] == "/api/documents"


def test_an_http_refusal_is_an_answer_not_an_exception() -> None:
    envelope = {"error": {"code": "declared_checksum_mismatch", "message": "no"}}
    _FakeConnection.script = {"response": _Response(422, json.dumps(envelope).encode())}

    assert _transport().post_document(PAYLOAD, headers=HEADERS) == (422, envelope)


def test_a_refused_connection_is_proven_never_sent() -> None:
    _FakeConnection.script = {"connect": ConnectionRefusedError("refused")}
    with pytest.raises(ArchiveDeliveryNotSentError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_a_dns_failure_is_proven_never_sent() -> None:
    _FakeConnection.script = {"connect": socket.gaierror("name or service not known")}
    with pytest.raises(ArchiveDeliveryNotSentError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_a_connect_timeout_is_proven_never_sent() -> None:
    """A deadline expiring while CONNECTING is the one timeout that proves absence:
    no byte ever left, so it must not be confused with a post-send deadline."""

    _FakeConnection.script = {"connect": TimeoutError("timed out")}
    with pytest.raises(ArchiveDeliveryNotSentError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_a_reset_while_sending_is_an_unknown_outcome() -> None:
    """Bytes may have left before the reset; the request may sit whole at Archive."""

    _FakeConnection.script = {"request": ConnectionResetError("reset by peer")}
    with pytest.raises(ArchiveOutcomeUnknownError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_a_response_deadline_is_an_unknown_outcome() -> None:
    _FakeConnection.script = {"response": socket.timeout("read timed out")}
    with pytest.raises(ArchiveOutcomeUnknownError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_a_lost_response_is_an_unknown_outcome() -> None:
    """RemoteDisconnected and a garbled status line arrive as HTTPException, not
    OSError -- both mean the request was accepted and the answer went missing."""

    _FakeConnection.script = {"response": http.client.RemoteDisconnected("closed")}
    with pytest.raises(ArchiveOutcomeUnknownError):
        _transport().post_document(PAYLOAD, headers=HEADERS)

    _FakeConnection.script = {"response": http.client.BadStatusLine("garbage")}
    with pytest.raises(ArchiveOutcomeUnknownError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_an_unparseable_body_is_an_empty_answer_never_a_crash() -> None:
    """Archive's status is authoritative even when a proxy garbles the body; the
    status must still reach the outcome mapping instead of dying in the parser."""

    _FakeConnection.script = {"response": _Response(200, b"\xff\xfenot json")}
    assert _transport().post_document(PAYLOAD, headers=HEADERS) == (200, {})
    _FakeConnection.script = {"response": _Response(200, b'["a","list"]')}
    assert _transport().post_document(PAYLOAD, headers=HEADERS) == (200, {})


def test_only_http_urls_are_accepted() -> None:
    """The custody authority is an HTTP service; anything else in configuration is
    a mistake to refuse at startup, not to attempt at delivery time."""

    with pytest.raises(ValueError):
        StdlibArchiveTransport("file:///etc/passwd", timeout_seconds=2.0)
    with pytest.raises(ValueError):
        StdlibArchiveTransport("archive.test:8150", timeout_seconds=2.0)
