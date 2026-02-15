# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP-compatible FastAPI server that redacts sensitive network data (IPv4, IPv6, MAC addresses) from text before AI processing. Sits in front of Claude/OpenCode as a privacy layer. Runs on Oracle Linux with uvicorn on port 10694.

## Build & Run Commands

```bash
# Install dependencies (Poetry required)
poetry install

# Run the server
uvicorn redact_mcp.main:app --host 0.0.0.0 --port 10694

# Run all tests
pytest

# Run a single test file
pytest tests/test_redactor.py

# Run a specific test
pytest tests/test_redactor.py::test_function_name -v
```

The virtual environment is at `./mcp/` (add to Poetry config or activate manually).

## Architecture

**Package:** `src/redact_mcp/`

- `main.py` — FastAPI app entry point. Two endpoints: `POST /redact` and `GET /health`
- `models.py` — Pydantic v2 request/response schemas (input text → redacted_text + mapping_id + mapping_count)
- `redactor.py` — Core redaction engine: compiled regex for IPv4/IPv6/MAC, per-request instances with random or HMAC-SHA256 deterministic replacement
- `storage.py` — Thread-safe in-memory mapping store (future: Redis)
- `logging_config.py` — Structured JSON logging (never logs raw data)

**Data flow:** Client sends raw network text → `/redact` endpoint validates via Pydantic → Redactor engine detects and replaces sensitive patterns → returns redacted text with UUID-keyed mapping

## Key Constraints

- Python 3.11+, FastAPI, Pydantic v2, Poetry packaging
- No global mutable state — thread-safe storage required
- Regex patterns must be safe against ReDoS attacks
- Never log raw/sensitive input
- Input size limit enforcement (recommended max 1MB)
- No insecure randomness for replacement values
- Must run as non-root user
- Oracle Linux deployment target

## AI Development Workflow

This project uses a multi-agent workflow (see `docs/ai-workflow.md`):
- **Claude** generates production code per `ai/claude_build_prompt.md`
- **OpenCode** validates security per `ai/opencode_validate_prompt.md`
- **CodeRabbit** reviews PRs per `ai/coderabbit_review.md`

Sandbox configs for agents are in `config/`.

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/redact` | Redact sensitive data from input text |
| GET | `/health` | Service health check |

POST `/redact` accepts `{"text": "..."}` and returns `{"mapping_id": "uuid", "redacted_text": "...", "mapping_count": N}`.
