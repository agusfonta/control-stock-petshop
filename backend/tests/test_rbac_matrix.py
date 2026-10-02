"""Matriz RBAC: solo duena crea usuarios (C-03 task 4.1, RED-first)."""

from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)

USUARIOS_URL = "/api/usuarios"
LOGIN_URL = "/api/auth/login"

NUEVO_EMAIL = "nuevo-mostrado@test.only"
NUEVO_PASSWORD = "test-only-nuevo-password"


async def _token(client, email: str, password: str) -> str:
    login = await client.post(
        LOGIN_URL, json={"email": email, "password": password}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def test_mostrador_no_puede_crear_usuarios(client) -> None:
    token = await _token(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.post(
        USUARIOS_URL,
        json={"email": NUEVO_EMAIL, "password": NUEVO_PASSWORD, "rol": "mostrador"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_anonimo_no_puede_crear_usuarios(client) -> None:
    response = await client.post(
        USUARIOS_URL,
        json={"email": NUEVO_EMAIL, "password": NUEVO_PASSWORD, "rol": "mostrador"},
    )
    assert response.status_code == 401


async def test_duena_crea_mostrador_y_login_ok(client) -> None:
    token = await _token(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        USUARIOS_URL,
        json={"email": NUEVO_EMAIL, "password": NUEVO_PASSWORD, "rol": "mostrador"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == NUEVO_EMAIL
    assert body["rol"] == "mostrador"
    assert body["activo"] is True
    assert body["id"]
    assert "password" not in body
    assert "password_hash" not in body

    login = await client.post(
        LOGIN_URL, json={"email": NUEVO_EMAIL, "password": NUEVO_PASSWORD}
    )
    assert login.status_code == 200


async def test_no_hay_registro_publico(client) -> None:
    """Sin token ninguna variante crea usuarios (401, nada cambia)."""
    for payload in [
        {"email": "pub1@test.only", "password": NUEVO_PASSWORD, "rol": "mostrador"},
        {"email": "pub2@test.only", "password": NUEVO_PASSWORD, "rol": "duena"},
    ]:
        response = await client.post(USUARIOS_URL, json=payload)
        assert response.status_code == 401
    retry = await client.post(
        LOGIN_URL, json={"email": "pub1@test.only", "password": NUEVO_PASSWORD}
    )
    assert retry.status_code == 401


async def test_duena_crea_duena_ok(client) -> None:
    token = await _token(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.post(
        USUARIOS_URL,
        json={
            "email": "otra-duena@test.only",
            "password": "test-only-otra-password",
            "rol": "duena",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["rol"] == "duena"


async def test_email_duplicado_409(client) -> None:
    token = await _token(client, DUENA_EMAIL, DUENA_PASSWORD)
    payload = {
        "email": "duplicado@test.only",
        "password": "test-only-dup-password",
        "rol": "mostrador",
    }
    primera = await client.post(
        USUARIOS_URL,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert primera.status_code == 201
    segunda = await client.post(
        USUARIOS_URL,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert segunda.status_code == 409


async def test_rol_invalido_422(client) -> None:
    token = await _token(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.post(
        USUARIOS_URL,
        json={
            "email": "rol-malo@test.only",
            "password": "test-only-rol-password",
            "rol": "admin",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_usuario_desactivado_pierde_acceso(client, db_session_factory) -> None:
    from app.models import Usuario

    token = await _token(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    me_antes = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_antes.status_code == 200
    with db_session_factory() as session:
        user = session.query(Usuario).filter_by(email=MOSTRADOR_EMAIL).one()
        user.activo = False
        session.commit()
    me_despues = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_despues.status_code == 401
