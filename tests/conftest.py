"""Test configuration for the redaction service."""

import os

import pytest

from redact_mcp.config import get_settings

os.environ.setdefault("MCP_DETERMINISTIC_SECRET", "test-deterministic-secret-key-1234567890")


@pytest.fixture(autouse=True)
def reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
