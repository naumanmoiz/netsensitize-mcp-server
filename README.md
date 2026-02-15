# NetSensitize MCP Server

MCP-compatible FastAPI server that redacts sensitive network data (IPv4, IPv6, MAC addresses) from text before AI processing. Sits in front of Claude/OpenCode as a privacy layer.

## Quickstart

```bash
# Install dependencies (Poetry required)
poetry install

# Required secret for deterministic mode
export MCP_DETERMINISTIC_SECRET="change-me-super-secret-string"

# (Optional) Redis backend
export MCP_REDIS_URL="redis://localhost:6379/0"

# Run the server
poetry run uvicorn redact_mcp.main:app --host 0.0.0.0 --port 10694

# Run tests (coverage threshold enforced at 95%)
poetry run pytest
```

## API

### `GET /health`

Returns `{"status": "ok"}` with HTTP 200.

### `POST /redact`

Accepts JSON or plain text. Returns redacted text with a mapping ID.

**JSON request:**
```bash
curl -X POST http://localhost:10694/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "Server 192.168.1.10 MAC 00:11:22:33:44:55", "mode": "random"}'
```

**Plain text request:**
```bash
curl -X POST http://localhost:10694/redact \
  -H "Content-Type: text/plain" \
  -d 'Router at 10.0.0.1'
```

**Response:**
```json
{
  "mapping_id": "uuid",
  "redacted_text": "Server 43.112.7.201 MAC a1:b2:c3:d4:e5:f6",
  "mapping_count": 2
}
```

**Modes:**
- `random` (default) — cryptographically random replacements
- `deterministic` — HMAC-SHA256 derived; consistent across requests when `MCP_DETERMINISTIC_SECRET` is set

## Architecture

```
src/redact_mcp/
  __init__.py         # Package init, __version__
  config.py           # Pydantic settings with env-driven configuration
  main.py             # FastAPI app, middleware orchestration, endpoints
  models.py           # Pydantic v2 schemas
  redactor.py         # Core regex-based redaction engine
  storage.py          # In-memory and Redis mapping stores with TTL
  rate_limiter.py     # Sliding window rate limiter
  middleware.py       # Request context, size, timeout, logging, and rate limit middleware
  logging_config.py   # Structured JSON logging
```

**Data flow:** Client sends raw text -> `/redact` validates via Pydantic -> `RedactorEngine` detects and replaces IPv4/IPv6/MAC -> returns redacted text with UUID-keyed mapping.

**Pattern priority:** IPv6 is matched before IPv4 to prevent partial matches on embedded addresses (e.g., `::ffff:192.168.1.1`).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_DETERMINISTIC_SECRET` | _required_ | HMAC key for deterministic mode (32+ chars). |
| `MCP_MAX_PAYLOAD_BYTES` | `1048576` | Maximum allowed request payload size. |
| `MCP_RATE_LIMIT_REQUESTS` | `120` | Allowed requests per IP within the window. |
| `MCP_RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit sliding window in seconds. |
| `MCP_REQUEST_TIMEOUT_SECONDS` | `15` | Request processing timeout. |
| `MCP_MAPPING_TTL_SECONDS` | `86400` | Mapping retention TTL (in-memory and Redis). |
| `MCP_REDIS_URL` | _unset_ | Enable Redis-backed mapping store when provided. |
| `MCP_REDIS_SSL` | `false` | Toggle TLS for Redis connections. |

## Security

- Deterministic replacements backed by user-provided HMAC secret
- ReDoS-hardened regex patterns with exhaustive fuzz tests
- Per-request engine instances, thread-safe stores, and TTL eviction to prevent leakage
- Structured JSON logging without raw payload retention (logs written to `docs/logs/*.jsonl`)
- Centralized exception handling, rate limiting, and payload guards
- Optional Redis backend for horizontal scaling with readiness and graceful shutdown checks
- Non-root Docker image (`oraclelinux:9-slim`) with uvicorn on port 10694

## Deployment (systemd)

```bash
# Copy service file
sudo cp redact-mcp.service /etc/systemd/system/

# Create service user
sudo useradd -r -s /sbin/nologin redactmcp

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now redact-mcp.service
```

## Development

```bash
# Run tests with coverage
poetry run pytest --cov=redact_mcp --cov-report=term-missing

# Run a single test
poetry run pytest tests/test_redactor.py::TestIPv4Replacement::test_single_ipv4 -v
```

Target: Python 3.11+, Oracle Linux, port 10694.

## Docker

```bash
# Build the container
docker build -t netsensitize:latest .

# Run (deterministic mode requires a secret)
docker run -p 10694:10694 \
  -e MCP_DETERMINISTIC_SECRET="change-me-super-secret-string" \
  netsensitize:latest
```

The image runs as a non-root user and exposes uvicorn on port `10694`.
