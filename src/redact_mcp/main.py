"""FastAPI application entry point for the redaction MCP server."""

from __future__ import annotations

import importlib
import json
import time
from contextlib import asynccontextmanager
from json import JSONDecodeError

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from .config import AppSettings, get_settings
from .logging_config import setup_logging
from .middleware import (
    PayloadSizeMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    RequestTimeoutMiddleware,
    StructuredLoggingMiddleware,
)
from .models import HealthResponse, RedactRequest, RedactResponse
from .rate_limiter import SlidingWindowRateLimiter
from .redactor import RedactorEngine
from .storage import BaseMappingStore, InMemoryMappingStore, RedisMappingStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger = setup_logging(
        log_directory=settings.log_directory,
        level="INFO",
        environment=settings.environment,
    )

    app.state.settings = settings
    app.state.logger = logger

    if settings.redis_url:
        try:
            redis_asyncio = importlib.import_module("redis.asyncio")  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:  # pragma: no cover - configuration guard
            raise RuntimeError(
                "redis dependency not installed; required for Redis backend"
            ) from exc

        redis_client = redis_asyncio.Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,
            ssl=settings.redis_ssl,
        )
        mapping_store: BaseMappingStore = RedisMappingStore(
            redis_client,
            ttl_seconds=settings.mapping_ttl_seconds,
        )
        app.state.redis = redis_client
    else:
        mapping_store = InMemoryMappingStore(
            ttl_seconds=settings.mapping_ttl_seconds,
            cleanup_interval_seconds=settings.cleanup_interval_seconds,
        )

    await mapping_store.startup()
    app.state.mapping_store = mapping_store
    app.state.rate_limiter = SlidingWindowRateLimiter(
        settings.rate_limit_requests, settings.rate_limit_window_seconds
    )
    app.state.ready = True

    try:
        yield
    finally:
        app.state.ready = False
        await app.state.rate_limiter.reset()
        await mapping_store.shutdown()
        if settings.redis_url and hasattr(app.state, "redis"):
            await app.state.redis.close()


def _log_timeout(request: Request) -> None:
    logger = getattr(request.app.state, "logger", None)
    if logger:
        logger.warning(
            "Request timed out",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "path": request.url.path,
            },
        )


app = FastAPI(
    title="Redact MCP Server",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(PayloadSizeMiddleware)
app.add_middleware(
    RequestTimeoutMiddleware,
    timeout_seconds=None,
    on_timeout=_log_timeout,
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger = getattr(request.app.state, "logger", None)
    if logger:
        logger.warning(
            "HTTP error",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "status_code": exc.status_code,
                "path": request.url.path,
            },
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger = getattr(request.app.state, "logger", None)
    if logger:
        logger.warning(
            "Validation error",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "path": request.url.path,
            },
        )
    return JSONResponse(
        status_code=400,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger = getattr(request.app.state, "logger", None)
    if logger:
        logger.error(
            "Internal server error",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "path": request.url.path,
                "error": exc.__class__.__name__,
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/health/ready", response_model=HealthResponse)
async def health_ready(request: Request):
    try:
        store: BaseMappingStore = request.app.state.mapping_store
        await store.count()
        if not request.app.state.ready:
            raise RuntimeError("Service not ready")
    except Exception:
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service unavailable"},
        )
    return HealthResponse()


@app.post("/redact", response_model=RedactResponse)
async def redact(request: Request):
    started_at = getattr(request.state, "started_at", time.monotonic())
    logger = getattr(request.app.state, "logger", None)
    settings: AppSettings = request.app.state.settings
    store: BaseMappingStore = request.app.state.mapping_store

    body = getattr(request.state, "body", None)
    if body is None:
        body = await request.body()

    content_type = request.headers.get("content-type", "")

    try:
        if "text/plain" in content_type:
            text = body.decode("utf-8", errors="replace")
            redact_request = RedactRequest(text=text)
        else:
            data = json.loads(body)
            redact_request = RedactRequest.model_validate(data)
    except (UnicodeDecodeError, JSONDecodeError):
        return JSONResponse(status_code=400, content={"detail": "Invalid request body"})
    except ValidationError as exc:
        return JSONResponse(
            status_code=400,
            content={"detail": "Validation error", "errors": exc.errors()},
        )

    engine = RedactorEngine(
        mode=redact_request.mode,
        deterministic_secret=settings.deterministic_secret_bytes,
    )
    redacted_text, mapping = engine.redact(redact_request.text)

    await store.save(engine.mapping_id, mapping)

    elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)
    client_ip = request.client.host if request.client else "unknown"

    if logger:
        logger.info(
            "Redaction completed",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "redaction_mode": redact_request.mode.value,
                "mapping_count": len(mapping),
                "processing_time_ms": elapsed_ms,
                "client_ip": client_ip,
            },
        )

    return RedactResponse(
        mapping_id=engine.mapping_id,
        redacted_text=redacted_text,
        mapping_count=len(mapping),
    )
