"""Flags de la cookie de refresh (C-03 task 5.3)."""

import httpx
import pytest

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD

LOGIN_URL = "/api/auth/login"
PROD_SECRET = "test-only-ephemeral-prod-secret-0123456789abcdef"


async def test_login_setea_cookie_httponly_samesite_lax(client) -> None:
    response = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    lowered = set_cookie.lower()
    assert "refresh_token=" in lowered
    assert "httponly" in lowered
    assert "samesite=lax" in lowered.replace(" ", "")
    assert "secure" not in lowered  # http local/dev: sin Secure por design


async def test_cookie_secure_en_prod(
    db_session_factory, fake_redis, seed_users
) -> None:
    from app import deps
    from app.core.config import Settings
    from app.main import create_app

    prod_settings = Settings(
        _env_file=None, env="prod", secret_key=PROD_SECRET
    )
    app = create_app()

    def _override_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = _override_db
    app.dependency_overrides[deps.get_redis] = lambda: fake_redis
    app.dependency_overrides[deps.get_settings] = lambda: prod_settings

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
        )
    assert response.status_code == 200
    lowered = response.headers.get("set-cookie", "").lower()
    assert "httponly" in lowered
    assert "secure" in lowered


async def test_refresh_tambien_setea_cookie_segura(client) -> None:
    login = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    assert login.status_code == 200
    rotated = await client.post("/api/auth/refresh")
    assert rotated.status_code == 200
    lowered = rotated.headers.get("set-cookie", "").lower()
    assert "refresh_token=" in lowered
    assert "httponly" in lowered
