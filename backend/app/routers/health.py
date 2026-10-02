"""Health check router (thin, no DB/Redis/auth by design — see C-01 design §3)."""

from fastapi import APIRouter

from app import __version__
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return service liveness without checking dependencies."""
    return HealthResponse(status="ok", version=__version__)
