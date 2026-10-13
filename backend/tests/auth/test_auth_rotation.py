"""Rotacion de refresh con revocacion (C-03 task 3.3, RED-first)."""

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD

LOGIN_URL = "/api/auth/login"
REFRESH_URL = "/api/auth/refresh"


async def _login(client):
    response = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    assert response.status_code == 200
    return response


async def test_refresh_valido_rota_el_par(client) -> None:
    login = await _login(client)
    viejo = login.cookies["refresh_token"]
    rotated = await client.post(REFRESH_URL)
    assert rotated.status_code == 200
    assert rotated.json()["access_token"]
    assert rotated.json()["token_type"] == "bearer"
    nuevo = rotated.cookies["refresh_token"]
    assert nuevo and nuevo != viejo


async def test_reuso_de_rotado_rechazado_y_revoca_cadena(client) -> None:
    login = await _login(client)
    viejo = login.cookies["refresh_token"]
    primera = await client.post(REFRESH_URL)
    assert primera.status_code == 200
    vigente = primera.cookies["refresh_token"]

    client.cookies.clear()
    reuso = await client.post(
        REFRESH_URL, headers={"Cookie": f"refresh_token={viejo}"}
    )
    assert reuso.status_code == 401

    # La cadena quedo revocada: ni el refresh vigente sirve ya.
    despues = await client.post(
        REFRESH_URL, headers={"Cookie": f"refresh_token={vigente}"}
    )
    assert despues.status_code == 401


async def test_refresh_expirado_401(client) -> None:
    from app.core.security import create_refresh_token

    expirado = create_refresh_token(subject="cualquiera", expires_days=-1)
    client.cookies.clear()
    response = await client.post(
        REFRESH_URL, headers={"Cookie": f"refresh_token={expirado}"}
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


async def test_refresh_revocado_401(client, fake_redis) -> None:
    from app.core.security import decode_token

    login = await _login(client)
    jti = decode_token(
        login.cookies["refresh_token"], expected_type="refresh"
    )["jti"]
    fake_redis.delete(f"auth:refresh:{jti}")
    crudo = login.cookies["refresh_token"]
    client.cookies.clear()
    response = await client.post(
        REFRESH_URL, headers={"Cookie": f"refresh_token={crudo}"}
    )
    assert response.status_code == 401


async def test_refresh_sin_cookie_401(client) -> None:
    client.cookies.clear()
    response = await client.post(REFRESH_URL)
    assert response.status_code == 401
