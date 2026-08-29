from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable
from typing import cast

import pytest
from fastapi import Request, Response
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.middleware.http_boundary import RequestBodySizeLimitMiddleware


def _request(
    *,
    chunks: Iterable[bytes],
    content_length: str | None = None,
) -> Request:
    body_chunks = deque(chunks)
    headers = [] if content_length is None else [(b"content-length", content_length.encode())]

    async def receive() -> dict[str, object]:
        if body_chunks:
            body = body_chunks.popleft()
            return {"type": "http.request", "body": body, "more_body": bool(body_chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/renders",
            "raw_path": b"/renders",
            "query_string": b"",
            "headers": headers,
            "client": ("test", 123),
            "server": ("render", 80),
        },
        receive,
    )


def _middleware(max_bytes: int) -> RequestBodySizeLimitMiddleware:
    async def app(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:  # pragma: no cover - dispatch is exercised directly
        del scope, receive, send

    return RequestBodySizeLimitMiddleware(app, max_request_body_bytes=max_bytes)


def _detail(response: Response) -> dict[str, object]:
    payload = cast(dict[str, object], json.loads(bytes(response.body)))
    return cast(dict[str, object], payload["detail"])


@pytest.mark.asyncio
async def test_streamed_body_without_content_length_is_measured() -> None:
    request = _request(chunks=(b"ab", b"cd"))

    async def call_next(request: Request) -> Response:  # pragma: no cover - must be rejected first
        raise AssertionError("Oversized body reached route handling.")

    response = await _middleware(3).dispatch(request, call_next)

    assert response.status_code == 413
    assert _detail(response)["code"] == "request_body_too_large"


@pytest.mark.asyncio
async def test_underdeclared_body_is_measured_from_received_bytes() -> None:
    request = _request(chunks=(b"ab", b"cd"), content_length="2")

    async def call_next(request: Request) -> Response:  # pragma: no cover - must be rejected first
        raise AssertionError("Under-declared oversized body reached route handling.")

    response = await _middleware(3).dispatch(request, call_next)

    assert response.status_code == 413
    assert _detail(response)["code"] == "request_body_too_large"


@pytest.mark.asyncio
@pytest.mark.parametrize("content_length", ["not-a-number", "-1"])
async def test_invalid_content_length_is_rejected_explicitly(content_length: str) -> None:
    request = _request(chunks=(b"{}",), content_length=content_length)

    async def call_next(request: Request) -> Response:  # pragma: no cover - must be rejected first
        raise AssertionError("Invalid Content-Length reached route handling.")

    response = await _middleware(64).dispatch(request, call_next)

    assert response.status_code == 400
    assert _detail(response)["code"] == "invalid_content_length"


@pytest.mark.asyncio
async def test_bounded_streamed_body_is_replayed_unchanged() -> None:
    request = _request(chunks=(b'{"report_', b'data":{}}'))

    async def call_next(request: Request) -> Response:
        assert await request.body() == b'{"report_data":{}}'
        return JSONResponse({"accepted": True})

    response = await _middleware(64).dispatch(request, call_next)

    assert response.status_code == 200
    assert json.loads(bytes(response.body)) == {"accepted": True}
