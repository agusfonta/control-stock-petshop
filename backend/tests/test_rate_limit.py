"""Rate limit de login 5/60s por IP+email (C-03 task 5.1, RED-first)."""

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD

LOGIN_URL = "/api/auth/login"
MAL = "test-only-clave-mal"


async def test_sexto_fallo_429_aun_con_credenciales_validas(client) -> None:
    for _ in range(5):
        fallido = await client.post(
            LOGIN_URL, json={"email": DUENA_EMAIL, "password": MAL}
        )
        assert fallido.status_code == 401
    bloqueado = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": MAL}
    )
    assert bloqueado.status_code == 429
    aunque_correcto = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    assert aunque_correcto.status_code == 429


async def test_exito_resetea_el_contador(client) -> None:
    for _ in range(3):
        await client.post(LOGIN_URL, json={"email": DUENA_EMAIL, "password": MAL})
    ok = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": DUENA_PASSWORD}
    )
    assert ok.status_code == 200
    for _ in range(5):
        fallido = await client.post(
            LOGIN_URL, json={"email": DUENA_EMAIL, "password": MAL}
        )
        assert fallido.status_code == 401
    sexto = await client.post(
        LOGIN_URL, json={"email": DUENA_EMAIL, "password": MAL}
    )
    assert sexto.status_code == 429
