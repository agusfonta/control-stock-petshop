"""Pydantic schemas (strict). C-01: solo HealthResponse."""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Respuesta de GET /api/health."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: str = Field(pattern=r"^ok$")
    version: str = Field(min_length=1)
