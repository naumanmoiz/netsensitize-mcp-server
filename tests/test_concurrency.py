"""Concurrency tests for the redaction API."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from redact_mcp.main import app
from redact_mcp.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_concurrent_requests_isolated():
    with TestClient(app, raise_server_exceptions=False) as client:
        client.app.state.rate_limiter = SlidingWindowRateLimiter(1000, 60)

        texts = [f"Request {idx} -> 10.0.{idx}.1" for idx in range(10)]

        async def send(text: str):
            return await asyncio.to_thread(
                client.post,
                "/redact",
                json={"text": text},
            )

        responses = await asyncio.gather(*(send(text) for text in texts))

    assert all(response.status_code == 200 for response in responses)

    mapping_ids = {response.json()["mapping_id"] for response in responses}
    assert len(mapping_ids) == len(responses)

    for original, response in zip(texts, responses):
        redacted = response.json()["redacted_text"]
        assert original not in redacted
