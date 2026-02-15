"""Pydantic v2 request/response schemas for the redaction API."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class RedactMode(str, Enum):
    """Redaction mode: random or deterministic replacement."""

    random = "random"
    deterministic = "deterministic"


class RedactRequest(BaseModel):
    """Request body for the /redact endpoint."""

    text: str = Field(..., min_length=1)
    mode: RedactMode = RedactMode.random


class RedactResponse(BaseModel):
    """Response body for the /redact endpoint."""

    mapping_id: UUID
    redacted_text: str
    mapping_count: int = Field(..., ge=0)


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""

    status: str = "ok"
