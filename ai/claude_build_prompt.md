# Claude Build Prompt

You are generating production-grade Python code for a FastAPI MCP redaction server.

Requirements:

- Python 3.11
- FastAPI
- uvicorn
- Port 10694
- Poetry packaging
- Deterministic mapping option
- IPv4, IPv6, MAC detection
- Thread-safe storage
- Input size limit
- Structured logging
- Health endpoint
- Oracle Linux compatible
- No global mutable state
- Pydantic v2
- Unit tests required
- No insecure randomness

Generate:

- redactor.py
- models.py
- main.py
- logging config
- tests
- pyproject.toml
- README.md

After each prompt
- save chats
- log process

Return only code.
No explanations.