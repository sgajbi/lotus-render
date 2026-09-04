"""The stdlib transport's translation table: statuses are answers, futures are typed.

The handoff treats "the deadline expired" (TimeoutError -> pending, reconcile) and
"the connection never carried the request" (OSError -> failed, redeliver) as different
futures, so the transport must keep them distinguishable -- urllib mixes both into
URLError and hides refusal bodies inside HTTPError.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

import pytest

from app.services.archive_handoff import StdlibArchiveTransport

PAYLOAD = {"metadata": {"archive_request_id": "areq_x"}, "content_base64": "aGk="}
HEADERS = {"Content-Type": "application/json", "X-Caller-Service": "lotus-render"}


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: Any) -> None:
        return None


def _transport() -> StdlibArchiveTransport:
    return StdlibArchiveTransport("http://archive.test", timeout_seconds=2.0)


def _posting(monkeypatch: pytest.MonkeyPatch, effect: Any) -> list[urllib.request.Request]:
    requests: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> Any:
        requests.append(request)
        assert timeout == 2.0
        if isinstance(effect, Exception):
            raise effect
        return effect

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return requests


def test_a_success_returns_the_parsed_body(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = _posting(monkeypatch, _Response(201, json.dumps({"document_id": "doc_1"}).encode()))

    status, body = _transport().post_document(PAYLOAD, headers=HEADERS)

    assert (status, body) == (201, {"document_id": "doc_1"})
    assert requests[0].full_url == "http://archive.test/documents"
    assert requests[0].get_method() == "POST"
    sent = requests[0].data
    assert isinstance(sent, bytes)
    assert json.loads(sent.decode()) == PAYLOAD


def test_an_http_refusal_is_an_answer_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = {"error": {"code": "declared_checksum_mismatch", "message": "no"}}
    _posting(
        monkeypatch,
        urllib.error.HTTPError(
            "http://archive.test/documents",
            422,
            "Unprocessable Entity",
            Message(),
            io.BytesIO(json.dumps(envelope).encode()),
        ),
    )

    status, body = _transport().post_document(PAYLOAD, headers=HEADERS)

    assert (status, body) == (422, envelope)


def test_a_wrapped_timeout_surfaces_as_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _posting(monkeypatch, urllib.error.URLError(TimeoutError("timed out")))
    with pytest.raises(TimeoutError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_a_bare_timeout_stays_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _posting(monkeypatch, TimeoutError("read timed out"))
    with pytest.raises(TimeoutError):
        _transport().post_document(PAYLOAD, headers=HEADERS)


def test_a_refused_connection_surfaces_as_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    _posting(monkeypatch, urllib.error.URLError(ConnectionRefusedError("refused")))
    with pytest.raises(OSError) as caught:
        _transport().post_document(PAYLOAD, headers=HEADERS)
    assert not isinstance(caught.value, TimeoutError)


def test_an_unparseable_body_is_an_empty_answer_never_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Archive's answer is authoritative even when a proxy garbles the body; the
    status must still reach the outcome mapping instead of dying in the parser."""

    _posting(monkeypatch, _Response(200, b"\xff\xfenot json"))
    assert _transport().post_document(PAYLOAD, headers=HEADERS) == (200, {})
    _posting(monkeypatch, _Response(200, b'["a","list"]'))
    assert _transport().post_document(PAYLOAD, headers=HEADERS) == (200, {})


def test_only_http_urls_are_accepted() -> None:
    """urlopen would happily fetch file:// -- the custody authority is an HTTP
    service, and anything else in configuration is a mistake to refuse at startup."""

    with pytest.raises(ValueError):
        StdlibArchiveTransport("file:///etc/passwd", timeout_seconds=2.0)
