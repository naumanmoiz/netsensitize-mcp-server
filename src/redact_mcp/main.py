"""FastAPI application entry point for the redaction MCP server."""

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging_config import setup_logging
from .models import HealthResponse, RedactMode, RedactRequest, RedactResponse
from .redactor import RedactorEngine
from .storage import mapping_store

MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB

logger = setup_logging()

app = FastAPI(
    title="Redact MCP Server",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# --- Middleware ---


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique request ID to every request/response."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            "Internal server error",
            extra={"request_id": request_id, "error": str(exc)},
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def payload_size_middleware(request: Request, call_next):
    """Reject payloads exceeding the size limit."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_PAYLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Payload too large"},
        )

    body = await request.body()
    if len(body) > MAX_PAYLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Payload too large"},
        )

    request.state.body = body
    return await call_next(request)


# --- Exception handlers ---


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Internal server error",
        extra={"request_id": request_id, "error": str(exc)},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@app.post("/redact", response_model=RedactResponse)
async def redact(request: Request):
    start = time.monotonic()
    request_id = getattr(request.state, "request_id", "unknown")

    body = getattr(request.state, "body", None)
    if body is None:
        body = await request.body()

    content_type = request.headers.get("content-type", "")

    if "text/plain" in content_type:
        text = body.decode("utf-8", errors="replace")
        redact_request = RedactRequest(text=text)
    else:
        # JSON (application/json or fallback)
        import json

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid JSON body"},
            )
        try:
            redact_request = RedactRequest(**data)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"detail": "Validation error"},
            )

    engine = RedactorEngine(mode=redact_request.mode)
    redacted_text, mapping = engine.redact(redact_request.text)

    mapping_store.save(engine.mapping_id, mapping)

    elapsed_ms = round((time.monotonic() - start) * 1000, 2)
    client_ip = request.client.host if request.client else "unknown"

    logger.info(
        "Redaction completed",
        extra={
            "request_id": request_id,
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
