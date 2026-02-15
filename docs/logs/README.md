# Log Storage Policy

This directory is used for structured JSONL session logs produced by the redaction service.

- Production deployments should redirect logs to a centralized sink instead of keeping them on disk.
- Local development logs are rotated by timestamp; files are ignored via `.gitignore`.
- Do **not** place raw customer payloads or secrets in this folder.

Placeholder file ensures the directory exists in source control.
