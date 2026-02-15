"""Structured JSON logging configuration.

Never logs raw input, redacted output, or actual IP/MAC values.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Single-line JSON log formatter."""

    SAFE_FIELDS = {
        "request_id",
        "redaction_mode",
        "mapping_count",
        "processing_time_ms",
        "client_ip",
        "error",
        "method",
        "path",
        "status_code",
        "environment",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in self.SAFE_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        if record.exc_info:
            log_entry["error"] = log_entry.get("error", "Unhandled exception")

        return json.dumps(log_entry, separators=(",", ":"))


def setup_logging(log_directory: Path, level: str = "INFO", environment: str = "production") -> logging.LoggerAdapter:
    """Configure structured logging to file and stderr."""

    logger = logging.getLogger("redact_mcp")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = JSONFormatter()

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    log_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    log_file = log_directory / f"session_{timestamp}.jsonl"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logging.LoggerAdapter(logger, extra={"environment": environment})
