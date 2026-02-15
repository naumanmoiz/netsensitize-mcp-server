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
3. Input size restriction
4. Strict regex patterns
5. No raw input logging
6. Non-root execution
7. Firewall port restriction

---

## Regex Safety

Patterns must:
- Avoid catastrophic backtracking
- Be bounded
- Use compiled regex

---

## Memory Controls

- Mapping expiration (future)
- Payload size cap
- Request rate limiting (future)

---

## Oracle Linux Hardening

- SELinux enforcing
- Firewalld configured
- Dedicated service user
- Systemd sandbox directives

---

## Recommended Enhancements

- Add Redis with TTL
- Enable rate limiting
- Add request logging without content
- Add audit event trail
- Add structured logging