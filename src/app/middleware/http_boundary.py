from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


def _declared_content_length(request: Request) -> int | None:
    raw_content_length = request.headers.get("content-length")
    if raw_content_length is None:
        return None
    try:
        declared_length = int(raw_content_length)
    except ValueError as exc:
        raise ValueError("Content-Length must be an integer.") from exc
    if declared_length < 0:
        raise ValueError("Content-Length must not be negative.")
    return declared_length


async def _read_limited_body(request: Request, max_bytes: int) -> bytes | None:
    chunks: list[bytes] = []
    total_size = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        total_size += len(chunk)
        if total_size > max_bytes:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _replay_body_for_downstream(request: Request, body: bytes) -> None:
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    setattr(request, "_body", body)
    setattr(request, "_receive", receive)


def _request_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get(
        "X-Correlation-Id"
    )
    trace_id = (
        getattr(request.state, "trace_id", None)
        or request.headers.get("X-Trace-Id")
        or request.headers.get("traceparent")
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
                "trace_id": trace_id,
            }
        },
    )


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_request_body_bytes: int) -> None:
        super().__init__(app)
        self._max_request_body_bytes = max_request_body_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            declared_length = _declared_content_length(request)
        except ValueError:
            return _request_error_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                code="invalid_content_length",
                message="Content-Length must be a non-negative integer.",
            )
        if declared_length is not None and declared_length > self._max_request_body_bytes:
            return _request_error_response(
                request,
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code="request_body_too_large",
                message="Request body exceeds the configured render API limit.",
            )

        body = await _read_limited_body(request, self._max_request_body_bytes)
        if body is None:
            return _request_error_response(
                request,
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code="request_body_too_large",
                message="Request body exceeds the configured render API limit.",
            )
        _replay_body_for_downstream(request, body)
        return await call_next(request)
