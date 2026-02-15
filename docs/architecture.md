# Redact MCP Server – Architecture

## Overview

Redact MCP Server is a FastAPI-based service designed to sanitize sensitive network data before it is processed by AI systems.

It replaces:
- IPv4 addresses
- IPv6 addresses
- MAC addresses

The service ensures that raw production network data is never directly exposed to AI systems such as Claude or Opencode.

---

## Design Goals

1. Prevent sensitive data leakage
2. Maintain deterministic mapping (optional mode)
3. Provide reversible redaction capability (future extension)
4. Run securely on Oracle Linux
5. Expose REST API on port 10694
6. Operate as an MCP-compatible preprocessing gateway

---

## High-Level Flow

Client → Redact MCP Server → AI (Claude / Opencode)

1. Client sends raw device output.
2. Redactor scans for IP/MAC patterns.
3. Values are replaced with randomized equivalents.
4. Mapping table stored in memory (or future backend store).
5. Redacted content returned to client.
6. Redacted content forwarded to AI.

---

## Core Components

### 1. API Layer (FastAPI)
- Request validation via Pydantic v2
- Response schema enforcement
- Health endpoint

### 2. Redactor Engine
- Regex-based detection
- Randomized replacement
- Optional deterministic mode
- Mapping store (in-memory initially)

### 3. Mapping Store
Current:
- In-memory dictionary

Future:
- Redis backend
- Expiration policies
- Encrypted storage

---

## Security Model

- No external network calls
- No raw config logging
- Input size limits
- Regex optimized to avoid ReDoS
- Thread-safe storage

---

## Deployment

- Oracle Linux
- uvicorn
- Non-root user
- Systemd service
- Firewall allow port 10694 only

---

## Future Enhancements

- Redis-backed mapping
- Reverse redaction endpoint
- Audit logging
- Prometheus metrics
- Rate limiting
- Structured logging
- Docker container support