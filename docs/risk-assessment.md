# Risk Assessment Summary

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Regex-based ReDoS | Low | High | Pre-compiled bounded regex with fuzz tests and performance guardrails. |
| Mapping leakage / uncontrolled growth | Medium | High | Per-request engine instances, TTL-based store pruning, optional Redis expiration. |
| Deterministic redaction predictability | Medium | Medium | HMAC with secret key; operators must rotate secret periodically. |
| Log disclosure of sensitive payloads | Low | High | Structured logging excludes raw bodies and maps; JSON formatter restricts fields. |
| Abuse via high request volume | Medium | Medium | Sliding-window rate limiting and request timeouts enforced by middleware. |
| Redis backend compromise | Low | High | Optional; recommend TLS/ACLs and separate network segment. |
| Configuration drift | Medium | Medium | Pydantic settings with explicit defaults and CI coverage for configuration paths. |
| Insider misuse of mapping data | Low | Medium | TTL eviction, absence of raw mapping retrieval endpoints, and recommendation to externalize audit logs. |

Residual risk is primarily tied to operational misconfiguration (secret management, Redis security). These areas require organizational controls outside the codebase and are called out in the production checklist.
