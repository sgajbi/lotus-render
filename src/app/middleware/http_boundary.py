from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_request_body_bytes: int) -> None:
        super().__init__(app)
        self._max_request_body_bytes = max_request_body_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                body_size = int(content_length)
            except ValueError:
                body_size = self._max_request_body_bytes + 1
            if body_size > self._max_request_body_bytes:
                correlation_id = getattr(
                    request.state, "correlation_id", None
                ) or request.headers.get("X-Correlation-Id")
                trace_id = (
                    getattr(request.state, "trace_id", None)
                    or request.headers.get("X-Trace-Id")
                    or request.headers.get("traceparent")
                )
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={
                        "detail": {
                            "code": "request_body_too_large",
                            "message": "Request body exceeds the configured render API limit.",
                            "correlation_id": correlation_id,
                            "trace_id": trace_id,
                        }
                    },
                )
        return await call_next(request)
