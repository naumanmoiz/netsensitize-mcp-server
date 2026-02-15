# Security Documentation

## Threat Model

The server processes potentially sensitive network configurations.

Risks include:
- Data leakage
- Regex denial of service
- Memory exhaustion
- Thread race conditions
- AI data exfiltration

---

## Controls Implemented

1. Sandbox-enabled AI execution
2. No network calls from AI
3. Input size restriction (1 MB default)
4. Strict regex patterns with fuzz testing and deterministic replacements
5. Structured logging with no raw input retention
6. Non-root execution (systemd + Docker)
7. Sliding-window rate limiting and request timeouts
8. Mapping TTL with in-memory cleanup and optional Redis backend

---

## Regex Safety

Patterns must:
- Avoid catastrophic backtracking
- Be bounded
- Use compiled regex

---

## Memory Controls

- Mapping expiration managed via per-store TTL
- Payload size cap enforced at middleware layer
- Rate limiting prevents abusive request floods

---

## Oracle Linux Hardening

- SELinux enforcing
- Firewalld configured
- Dedicated service user
- Systemd sandbox directives

---

## Recommended Enhancements

- Integrate audit event trail with tamper-evident storage
- Add Redis authentication / TLS certificates management guidance
- Implement automated secret rotation playbooks for deterministic key
- Extend mapping store metrics to external observability platforms
