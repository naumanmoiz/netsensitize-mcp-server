"""Basic performance regression tests."""

import time

from redact_mcp.redactor import RedactorEngine


def test_redactor_large_payload_performance():
    engine = RedactorEngine()
    text = "".join(
        f"Host {i}.0.0.{i} has MAC aa:bb:cc:dd:ee:{i:02x}\n" for i in range(500)
    )

    start = time.perf_counter()
    redacted, mapping = engine.redact(text)
    duration = time.perf_counter() - start

    assert len(mapping) >= 500
    assert duration < 1.0
