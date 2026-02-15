"""Additional coverage for infrastructure components."""

import asyncio
import importlib
import logging
import time
import types
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from redact_mcp.logging_config import setup_logging
from redact_mcp.main import (
    _log_timeout,
    lifespan,
    http_exception_handler,
    redact as redact_endpoint,
    validation_exception_handler,
)
from redact_mcp.middleware import (
    PayloadSizeMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    RequestTimeoutMiddleware,
    StructuredLoggingMiddleware,
    _client_identifier,
)
from redact_mcp.rate_limiter import SlidingWindowRateLimiter
from redact_mcp.storage import InMemoryMappingStore, RedisMappingStore
from redact_mcp.models import RedactResponse
from redact_mcp.redactor import IPV4_RE, IPV6_RE, MAC_RE, RedactorEngine
from redact_mcp.config import get_settings


class DummyRedis:
    """In-memory stand-in for Redis used in tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.closed = False
        self._scan_calls = 0

    @classmethod
    def from_url(cls, *_args, **_kwargs):
        return cls()

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    async def scan(self, cursor: int = 0, match: str | None = None, count: int | None = None):
        keys = [key for key in self._store if match is None or key.startswith(match.rstrip("*"))]
        self._scan_calls += 1
        if self._scan_calls == 1:
            return 1, keys
        return 0, []

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self.closed = True


def test_rate_limiter_invalid_parameters():
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(0, 60)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(10, 0)


@pytest.mark.asyncio
async def test_rate_limiter_window(monkeypatch):
    limiter = SlidingWindowRateLimiter(1, 1)
    current = 1000.0

    def fake_monotonic() -> float:
        return current

    monkeypatch.setattr("redact_mcp.rate_limiter.time.monotonic", fake_monotonic)

    allowed, _ = await limiter.check("client")
    assert allowed

    current += 0.1
    allowed, retry_after = await limiter.check("client")
    assert not allowed
    assert retry_after is not None

    current += 1.1
    allowed, _ = await limiter.check("client")
    assert allowed


@pytest.mark.asyncio
async def test_inmemory_store_delete_and_count():
    store = InMemoryMappingStore(ttl_seconds=None, cleanup_interval_seconds=1)
    await store.startup()

    mapping_id = uuid4()
    await store.save(mapping_id, {"value": "replacement"})
    assert await store.count() == 1

    assert await store.delete(mapping_id) is True
    assert await store.count() == 0

    await store.shutdown()


@pytest.mark.asyncio
async def test_redis_store_operations(monkeypatch):
    monkeypatch.setattr("redact_mcp.storage.redis_asyncio", object(), raising=False)
    client = DummyRedis()
    store = RedisMappingStore(client, ttl_seconds=60)

    await store.startup()

    mapping_id = uuid4()
    await store.save(mapping_id, {"value": "replacement"})
    assert await store.get(mapping_id) == {"value": "replacement"}
    assert await store.count() == 1
    assert await store.delete(mapping_id)
    assert await store.count() == 0

    await store.shutdown()
    assert client.closed


@pytest.mark.asyncio
async def test_redis_store_without_ttl(monkeypatch):
    monkeypatch.setattr("redact_mcp.storage.redis_asyncio", object(), raising=False)
    client = DummyRedis()
    store = RedisMappingStore(client, ttl_seconds=None)

    mapping_id = uuid4()
    await store.save(mapping_id, {"value": "replacement"})
    retrieved = await store.get(mapping_id)
    assert retrieved == {"value": "replacement"}

    await store.shutdown()

def test_setup_logging_creates_file(tmp_path: Path):
    base_logger = logging.getLogger("redact_mcp")
    original_handlers = base_logger.handlers[:]
    for handler in original_handlers:
        base_logger.removeHandler(handler)

    logger = setup_logging(tmp_path, level="info", environment="test")
    logger.info("structured log example")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("captured error")

    for handler in logger.logger.handlers:
        handler.flush()

    files = list(tmp_path.iterdir())
    assert files, "log file should be created"

    for handler in logger.logger.handlers:
        handler.close()
        base_logger.removeHandler(handler)
    for handler in original_handlers:
        base_logger.addHandler(handler)


@pytest.mark.asyncio
async def test_lifespan_redis_backend(monkeypatch):
    monkeypatch.setenv("MCP_REDIS_URL", "redis://localhost:6379/0")

    dummy_module = types.SimpleNamespace(Redis=DummyRedis)
    original_import = importlib.import_module

    def fake_import(name: str, package=None):
        if name == "redis.asyncio":
            return dummy_module
        return original_import(name, package=package)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    app = FastAPI()
    async with lifespan(app):
        assert isinstance(app.state.mapping_store, RedisMappingStore)
        assert getattr(app.state, "ready") is True

    assert isinstance(app.state.redis, DummyRedis)

    monkeypatch.delenv("MCP_REDIS_URL", raising=False)


def test_log_timeout_logs():
    class DummyLogger:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def warning(self, message: str, extra: dict | None = None) -> None:
            self.calls.append((message, extra or {}))

    dummy_logger = DummyLogger()
    request = types.SimpleNamespace(
        app=types.SimpleNamespace(state=types.SimpleNamespace(logger=dummy_logger)),
        state=types.SimpleNamespace(request_id="req-123"),
        url=types.SimpleNamespace(path="/redact"),
    )

    _log_timeout(cast(Any, request))

    assert dummy_logger.calls
    message, extra = dummy_logger.calls[0]
    assert "Request timed out" in message
    assert extra.get("request_id") == "req-123"


def test_payload_size_middleware_custom_limit():
    app = FastAPI()

    @app.post("/echo")
    async def echo_endpoint():
        return PlainTextResponse("ok")

    app.add_middleware(PayloadSizeMiddleware, max_payload_bytes=16)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/echo", content="A" * 32)
        assert response.status_code == 413


def test_request_timeout_middleware(monkeypatch):
    app = FastAPI()

    @app.post("/slow")
    async def slow_endpoint():
        await asyncio.sleep(0.05)
        return PlainTextResponse("done")

    app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=0, on_timeout=lambda _: None)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/slow")
        assert response.status_code == 504


def test_payload_size_middleware_without_settings():
    app = FastAPI()

    @app.post("/noop")
    async def noop():
        return PlainTextResponse("ok")

    app.add_middleware(PayloadSizeMiddleware)

    with TestClient(app, raise_server_exceptions=False) as client:
        app_state = cast(Any, client).app.state
        if hasattr(app_state, "settings"):
            delattr(app_state, "settings")
        response = client.post("/noop", content=b"hello")
        assert response.status_code == 200


def test_request_timeout_middleware_without_settings():
    app = FastAPI()

    @app.post("/quick")
    async def quick():
        return PlainTextResponse("ok")

    app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=None, on_timeout=lambda _: None)

    with TestClient(app, raise_server_exceptions=False) as client:
        app_state = cast(Any, client).app.state
        if hasattr(app_state, "settings"):
            delattr(app_state, "settings")
        response = client.post("/quick")
        assert response.status_code == 200


def test_rate_limit_middleware_without_limiter():
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return PlainTextResponse("pong")

    app.add_middleware(RateLimitMiddleware)

    with TestClient(app, raise_server_exceptions=False) as client:
        cast(Any, client).app.state.rate_limiter = None
        response = client.get("/ping")
        assert response.status_code == 200


def test_structured_logging_middleware_fallback_logger():
    async def dummy_app(scope, receive, send):  # type: ignore[unused-argument]
        raise RuntimeError("not used")

    middleware = StructuredLoggingMiddleware(dummy_app)
    request = types.SimpleNamespace(app=types.SimpleNamespace(state=types.SimpleNamespace(logger=None)))
    logger = middleware._logger(cast(Request, request))
    assert logger.name == "redact_mcp"


def test_client_identifier_variants():
    request = types.SimpleNamespace(headers={"x-forwarded-for": "1.1.1.1, 2.2.2.2"}, client=None)
    assert _client_identifier(cast(Request, request)) == "1.1.1.1"

    request2 = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="3.3.3.3"))
    assert _client_identifier(cast(Request, request2)) == "3.3.3.3"

    request3 = types.SimpleNamespace(headers={}, client=None)
    assert _client_identifier(cast(Request, request3)) == "unknown"


def test_redactor_random_replacements_format():
    engine = RedactorEngine()
    assert IPV4_RE.fullmatch(engine._random_replacement("ipv4"))
    assert IPV6_RE.fullmatch(engine._random_replacement("ipv6"))
    assert MAC_RE.fullmatch(engine._random_replacement("mac"))


def test_redactor_byte_conversions():
    assert IPV4_RE.fullmatch(RedactorEngine._ipv4_from_bytes(b"\x01\x02\x03\x04"))
    ipv6 = RedactorEngine._ipv6_from_bytes(bytes(range(16)))
    assert IPV6_RE.fullmatch(ipv6)
    assert MAC_RE.fullmatch(RedactorEngine._mac_from_bytes(bytes(range(6))))


@pytest.mark.asyncio
async def test_http_exception_handler_logs():
    logs: list[dict] = []

    class DummyLogger:
        def warning(self, _message: str, extra: dict | None = None) -> None:
            logs.append(extra or {})

    request = types.SimpleNamespace(
        app=types.SimpleNamespace(state=types.SimpleNamespace(logger=DummyLogger())),
        state=types.SimpleNamespace(request_id="req-404"),
        url=types.SimpleNamespace(path="/missing"),
    )
    response = await http_exception_handler(cast(Request, request), StarletteHTTPException(status_code=404, detail="Not Found"))
    assert response.status_code == 404
    assert logs and logs[0]["status_code"] == 404


@pytest.mark.asyncio
async def test_validation_exception_handler_logs():
    logs: list[dict] = []

    class DummyLogger:
        def warning(self, _message: str, extra: dict | None = None) -> None:
            logs.append(extra or {})

    request = types.SimpleNamespace(
        app=types.SimpleNamespace(state=types.SimpleNamespace(logger=DummyLogger())),
        state=types.SimpleNamespace(request_id="req-val"),
        url=types.SimpleNamespace(path="/redact"),
    )
    exc = RequestValidationError([{"loc": ("body", "text"), "msg": "Missing", "type": "value_error.missing"}])
    response = await validation_exception_handler(cast(Request, request), exc)
    assert response.status_code == 400
    assert logs


@pytest.mark.asyncio
async def test_redact_reads_body_when_not_cached():
    settings = get_settings()

    class DummyStore:
        def __init__(self) -> None:
            self.saved = None

        async def save(self, mapping_id, mapping):
            self.saved = (mapping_id, mapping)

    store = DummyStore()

    request = types.SimpleNamespace(
        app=types.SimpleNamespace(state=types.SimpleNamespace(settings=settings, mapping_store=store, logger=None)),
        state=types.SimpleNamespace(request_id="req-body", started_at=time.monotonic()),
        headers={"content-type": "application/json"},
        client=types.SimpleNamespace(host="127.0.0.1"),
    )

    async def body() -> bytes:
        return b'{"text": "10.0.0.1"}'

    request.body = body

    response = cast(RedactResponse, await redact_endpoint(cast(Request, request)))
    assert response.mapping_count == 1
    assert store.saved is not None
