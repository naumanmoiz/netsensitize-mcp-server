# Performance Review — 2026-02-15

## Summary

- Regex execution validated with Hypothesis fuzz tests (`tests/test_fuzz.py`) and performance guard (`tests/test_performance.py`). Redaction of 500 mixed addresses completes < 1s on CI hardware.
- Cooperative rate limiting and payload guards prevent pathological memory growth; background TTL eviction keeps mapping footprint bounded.
- Structured logging is single-line JSON (stderr + file) to minimize I/O overhead; consider forwarding to external sink in production.
- File I/O limited to session logs under `docs/logs/`; disable or redirect in containerized deployments.
- Optional Redis backend offloads memory pressure for long-lived mappings; ensure instance sizing aligns with `MCP_MAPPING_TTL_SECONDS`.

## Recommendations

1. Benchmark under representative traffic (1k RPS) to tune `MCP_RATE_LIMIT_*` and `MCP_REQUEST_TIMEOUT_SECONDS` baselines.
2. Enable Redis when mapping retention > 1 hour or concurrent requests > 100 to avoid memory spikes.
3. Add metrics instrumentation (Prometheus or OCI) for latency and rate-limit hit ratios in future iteration.
4. Consider enabling uvicorn access logs only in debug mode to avoid duplicate telemetry with structured middleware.
