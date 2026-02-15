# Security Audit — 2026-02-15

## Overview

OpenCode performed a deep security review of the NetSensitize MCP redaction server. The following table summarizes the issues identified and the remediations applied during this iteration.

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
| Deterministic mode inconsistent across requests | High | Fixed | Introduced HMAC derived from `MCP_DETERMINISTIC_SECRET` ensuring stable replacements. |
| Global mutable mapping store without TTL | High | Fixed | Replaced with dependency-injected stores (in-memory + Redis) including per-record TTL and background eviction. |
| Missing rate limiting and timeouts | Medium | Fixed | Added sliding-window rate limiter and ASGI timeout middleware configurable via environment. |
| Payload middleware lacked body reuse safeguards | Medium | Fixed | Middleware now stores the request body in state and respects configuration from settings. |
| Logging could fall back to default handlers with raw text | Medium | Fixed | Structured JSON logging enforced with sanitized fields only. |
| Optional Redis backend absent | Medium | Fixed | Added async Redis store with health checks, TTL enforcement, and graceful shutdown. |
| Lack of request correlation logging | Low | Fixed | Request context middleware now issues UUIDs and structured logging middleware records method/path/latency. |
| No concurrency regression coverage | Low | Fixed | Added async concurrency, fuzz, and performance tests with >95% coverage threshold. |

## Residual Risks

- Secrets management: Operators must provision and rotate `MCP_DETERMINISTIC_SECRET` securely (e.g., via Vault or OCI Secrets).
- Redis hardening: When enabling Redis, enforce ACLs/TLS and monitor key cardinality.
- Log retention: JSON logs are written to `docs/logs/`; in production they should be forwarded to a centralized, access-controlled sink.

## References

- `src/redact_mcp/config.py` — validated configuration contract.
- `src/redact_mcp/middleware.py` — new guard middleware implementations.
- `tests/test_internal_components.py` — security regression coverage.
