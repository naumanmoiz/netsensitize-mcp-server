# NetSensitize MCP Server

MCP-compatible FastAPI server that redacts sensitive network data (IPv4, IPv6, MAC addresses) from text before AI processing. Sits in front of Claude/OpenCode as a privacy layer.

## Quickstart

```bash
# Install dependencies (Poetry required)
poetry install

# Run the server
poetry run uvicorn redact_mcp.main:app --host 0.0.0.0 --port 10694

# Run tests
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
- `deterministic` — HMAC-SHA256 derived; consistent within a request, different across requests

## Architecture

```
src/redact_mcp/
  __init__.py         # Package init, __version__
  main.py             # FastAPI app, middleware, endpoints
  models.py           # Pydantic v2 schemas
  redactor.py         # Core regex-based redaction engine
  storage.py          # Thread-safe in-memory mapping store
  logging_config.py   # Structured JSON logging
```

**Data flow:** Client sends raw text -> `/redact` validates via Pydantic -> `RedactorEngine` detects and replaces IPv4/IPv6/MAC -> returns redacted text with UUID-keyed mapping.

**Pattern priority:** IPv6 is matched before IPv4 to prevent partial matches on embedded addresses (e.g., `::ffff:192.168.1.1`).

## Security

- Per-request engine instances — no shared mutable state
- `secrets` module for random replacements (CSPRNG)
- HMAC-SHA256 with per-request salt for deterministic mode
- 1 MB payload size limit
- No raw data in logs
- Regex patterns designed to resist ReDoS
- Runs as non-root via systemd hardening

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
