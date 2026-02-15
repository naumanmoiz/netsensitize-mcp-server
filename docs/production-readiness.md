# Production Readiness Checklist

- [x] Deterministic secret (`MCP_DETERMINISTIC_SECRET`) configured and stored in secure secret manager
- [x] Optional Redis backend validated with TLS/ACL if `MCP_REDIS_URL` is supplied
- [x] Rate limiting parameters tuned for deployment traffic profile
- [x] Request timeout calibrated to upstream SLAs
- [x] Mapping TTL set according to data retention policy (default 24h)
- [x] Structured logs shipped to centralized SIEM (rotate/remove `docs/logs/` in production)
- [x] Health (`/health`) and readiness (`/health/ready`) probes wired into orchestration platform
- [x] CI pipeline enforcing tests and 95% coverage (`.github/workflows/ci.yml`)
- [x] Docker image built from `oraclelinux:9-slim` with non-root runtime (`Dockerfile`)
- [x] Observability hooks (metrics/log aggregation) verified in staging
- [x] Backup and recovery plan for Redis (if enabled)
- [ ] Incident response runbook updated with latest failure scenarios
