"""Custom FastAPI middleware components."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from .rate_limiter import SlidingWindowRateLimiter


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and timing metadata."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.started_at = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class PayloadSizeMiddleware(BaseHTTPMiddleware):
    """Reject requests exceeding configured payload size."""

    def __init__(self, app: ASGIApp, max_payload_bytes: int | None = None, settings_attr: str = "settings") -> None:
        super().__init__(app)
        self._max_payload_bytes = max_payload_bytes
        self._settings_attr = settings_attr

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        max_bytes = self._max_payload_bytes
        if max_bytes is None:
            settings = getattr(request.app.state, self._settings_attr, None)
            if settings is None:
                return await call_next(request)
            max_bytes = settings.max_payload_bytes

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            return JSONResponse(status_code=413, content={"detail": "Payload too large"})

        body = await request.body()
        if len(body) > max_bytes:
            return JSONResponse(status_code=413, content={"detail": "Payload too large"})

        request.state.body = body
        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Enforce a maximum request processing time."""

    def __init__(
        self,
        app: ASGIApp,
        timeout_seconds: int | None,
        on_timeout: Callable[[Request], None],
        settings_attr: str = "settings",
    ) -> None:
        super().__init__(app)
        self._timeout_seconds = timeout_seconds
        self._on_timeout = on_timeout
        self._settings_attr = settings_attr

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        timeout_seconds = self._timeout_seconds
        if timeout_seconds is None:
            settings = getattr(request.app.state, self._settings_attr, None)
            if settings is None:
                return await call_next(request)
            timeout_seconds = settings.request_timeout_seconds

        try:
            async with asyncio.timeout(timeout_seconds):
                return await call_next(request)
        except asyncio.TimeoutError:
            self._on_timeout(request)
            return JSONResponse(
                status_code=504,
                content={"detail": "Request timed out"},
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply IP-based rate limiting."""

    def __init__(
        self,
        app: ASGIApp,
        limiter: SlidingWindowRateLimiter | None = None,
        limiter_attr: str = "rate_limiter",
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._limiter_attr = limiter_attr

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        limiter = self._limiter or getattr(request.app.state, self._limiter_attr, None)
        if limiter is None:
            return await call_next(request)
        client_host = _client_identifier(request)
        allowed, retry_after = await limiter.check(client_host)
        if not allowed:
            headers = {"Retry-After": f"{retry_after:.0f}"} if retry_after else None
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers=headers,
            )
        return await call_next(request)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Emit structured request logs after response generation."""

    def __init__(self, app: ASGIApp, logger_attr: str = "logger") -> None:
        super().__init__(app)
        self._logger_attr = logger_attr

    def _logger(self, request: Request):
        logger = getattr(request.app.state, self._logger_attr, None)
        if logger is None:
            import logging

            return logging.getLogger("redact_mcp")
        return logger

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        started_at = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.monotonic() - started_at) * 1000, 2)
            self._logger(request).error(
                "Request failed",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "processing_time_ms": duration_ms,
                },
            )
            raise

        duration_ms = round((time.monotonic() - started_at) * 1000, 2)
        self._logger(request).info(
            "Request completed",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "processing_time_ms": duration_ms,
            },
        )
        return response


def _client_identifier(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
