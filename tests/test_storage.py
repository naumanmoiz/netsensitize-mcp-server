"""Tests for mapping storage backends."""

import asyncio
from uuid import uuid4

import pytest

from redact_mcp.storage import InMemoryMappingStore


@pytest.mark.asyncio
async def test_inmemory_store_ttl_expiration():
    store = InMemoryMappingStore(ttl_seconds=1, cleanup_interval_seconds=1)
    await store.startup()

    mapping_id = uuid4()
    await store.save(mapping_id, {"10.0.0.1": "20.0.0.1"})
    assert await store.get(mapping_id) == {"10.0.0.1": "20.0.0.1"}

    await asyncio.sleep(1.2)
    assert await store.get(mapping_id) is None

    await store.shutdown()
