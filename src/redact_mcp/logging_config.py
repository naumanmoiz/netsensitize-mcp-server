"""Structured JSON logging configuration.

Never logs raw input, redacted output, or actual IP/MAC values.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Single-line JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in (
            "request_id",
            "redaction_mode",
            "mapping_count",
            "processing_time_ms",
            "client_ip",
            "error",
        ):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        return json.dumps(log_entry)


def setup_logging() -> logging.Logger:
    """Configure structured logging to file and stderr."""
    logger = logging.getLogger("redact_mcp")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = JSONFormatter()

    # Stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    # File handler — log directory relative to project root
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "logs")
    log_dir = os.path.normpath(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"session_{timestamp}.json")

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
