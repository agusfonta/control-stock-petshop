"""Endpoints auth: login / me (C-03 task 3.1, RED-first)."""

from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    INACTIVO_EMAIL,
    INACTIVO_PASSWORD,
)

LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"


async def test_login_ok_devuelve_access_y_cookie(client) -> None:
    response = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "refresh_token" in response.cookies


async def test_login_password_incorrecto_401_generico(client) -> None:
    response = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": "test-only-clave-mal"}
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.cookies


async def test_login_email_inexistente_mismo_401(client) -> None:
    r1 = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": "test-only-clave-mal"}
    )
    r2 = await client.post(
        LOGIN_URL,
        json={"email": "nadie@test.only", "password": "test-only-clave-mal"},
    )
    assert r2.status_code == 401
    assert r1.json() == r2.json()


async def test_login_usuario_inactivo_401(client) -> None:
    response = await client.post(
        LOGIN_URL,
        json={"email": INACTIVO_EMAIL, "password": INACTIVO_PASSWORD},
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


async def test_me_con_token_devuelve_identidad(client) -> None:
    login = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    token = login.json()["access_token"]
    me = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == DUENA_EMAIL
    assert body["rol"] == "duena"
    assert body["activo"] is True
    assert body["id"]


async def test_me_sin_token_401(client) -> None:
    response = await client.get(ME_URL)
    assert response.status_code == 401


async def test_me_token_expirado_401(client) -> None:
    from app.core.security import create_access_token

    token = create_access_token(
        subject="cualquiera",
        rol="duena",
        secret_key="test-only-ephemeral-secret-key-0123456789",
        expires_minutes=-5,
    )
    response = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_me_token_manipulado_401(client) -> None:
    login = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    token = login.json()["access_token"] + "manipulado"
    response = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_login_sin_password_422(client) -> None:
    response = await client.post(LOGIN_URL, json={"email": DUENA_EMAIL})
    assert response.status_code == 422


async def test_login_email_invalido_422(client) -> None:
    response = await client.post(
        LOGIN_URL, json={"email": "no-es-email", "password": "test-only-x"}
    )
    assert response.status_code == 422


async def test_login_body_vacio_422(client) -> None:
    response = await client.post(LOGIN_URL, json={})
    assert response.status_code == 422


async def test_login_campo_extra_422(client) -> None:
    response = await client.post(
        LOGIN_URL,
        json={
            "email": DUENA_EMAIL,
            "password": DUENA_PASSWORD,
            "admin": True,
        },
    )
    assert response.status_code == 422
