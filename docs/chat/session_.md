# Build Session Log

## Prompt

Implement a complete MCP-compatible FastAPI redaction server that sanitizes network data (IPv4, IPv6, MAC) before AI processing. Per the plan in CLAUDE.md, with Poetry packaging, Oracle Linux deployment target, port 10694.

## Generated Files

| File | Purpose |
|------|---------|
| `src/redact_mcp/__init__.py` | Package init with `__version__` |
| `src/redact_mcp/models.py` | Pydantic v2 schemas (RedactRequest, RedactResponse, HealthResponse, RedactMode) |
| `src/redact_mcp/redactor.py` | Core redaction engine with compiled regex for IPv4/IPv6/MAC |
| `src/redact_mcp/storage.py` | Thread-safe in-memory mapping store |
| `src/redact_mcp/logging_config.py` | Structured JSON logging (never logs raw data) |
| `src/redact_mcp/main.py` | FastAPI app with middleware (payload limit, request ID) and endpoints |
| `tests/test_redactor.py` | Unit tests for redaction engine (~12 tests) |
| `tests/test_api.py` | Integration tests for API (~9 tests) |
| `pyproject.toml` | Fixed package path, added pytest-cov, pytest config |
| `.gitignore` | Expanded with Python/IDE/coverage patterns |
| `redact-mcp.service` | Hardened systemd unit file |
| `README.md` | Full project documentation |
| `CLAUDE.md` | Updated to reflect new file structure |

## Deleted Files

- `src/redact_mcp/redactory.py` (replaced by `redactor.py`)
- `src/redact_mcp/utils.py` (replaced by `storage.py` and `logging_config.py`)

## Security Decisions

1. Per-request `RedactorEngine` instances — zero shared mutable state
2. `secrets` module (CSPRNG) for random replacements
3. HMAC-SHA256 with per-request `secrets.token_bytes(32)` salt for deterministic mode
4. IPv6 matched before IPv4 to prevent partial match of `::ffff:` mapped addresses
5. 1 MB payload size limit enforced via middleware
6. No raw input/output in logs — only metadata (request_id, mode, mapping_count, timing)
7. Systemd unit runs as non-root with `NoNewPrivileges`, `ProtectSystem=strict`
8. Regex patterns use bounded alternations (no unbounded quantifiers) to resist ReDoS

## Assumptions

- In-memory mapping store (future: Redis)
- Single-process deployment (uvicorn without workers) for initial version
- Log files written to `docs/logs/` relative to project root

## Known Limitations

- Mapping store is not persistent across restarts
- No authentication on endpoints
- No rate limiting (should be handled by reverse proxy)
- IPv6 regex covers common forms but may not match every RFC 5952 edge case
