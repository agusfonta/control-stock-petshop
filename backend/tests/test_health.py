"""Smoke test for GET /api/health (C-01, no business rules)."""

import httpx
import pytest
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_health_ok() -> None:
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


@pytest.mark.asyncio
async def test_health_no_auth_no_db() -> None:
    """Health responds 200 without token and without DB/Redis (design §3)."""
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health", headers={"Authorization": ""})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


def test_health_response_schema_strict() -> None:
    from app.schemas import HealthResponse

    payload = HealthResponse(status="ok", version="0.1.0")
    assert payload.model_dump() == {"status": "ok", "version": "0.1.0"}
    with pytest.raises(ValidationError):
        HealthResponse(status="fail", version="0.1.0")
    with pytest.raises(ValidationError):
        HealthResponse.model_validate({"status": "ok", "version": "0.1.0", "extra": 1})
