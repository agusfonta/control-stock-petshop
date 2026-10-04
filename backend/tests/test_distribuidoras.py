"""CRUD de distribuidoras via API (C-06 task 2.1, RED-first).

Escritura solo duena (guards C-03); lectura cualquier usuario activo.
Borrado = soft-delete (activo=False), nunca fisico.
"""

from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)

DISTRIBUIDORAS_URL = "/api/distribuidoras"


def _distribuidora_payload(**overrides):
    payload = {"nombre": "Distri Sur", "cuit": "30-12345678-9"}
    payload.update(overrides)
    return payload


async def _login(client, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Crear ---


async def test_crear_distribuidora_201(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["nombre"] == "Distri Sur"
    assert body["cuit"] == "30-12345678-9"
    assert body["activo"] is True
    assert body["id"]
    assert body["created_at"]
    assert body["updated_at"]


async def test_crear_distribuidora_nombre_vacio_422(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.post(
        DISTRIBUIDORAS_URL,
        json=_distribuidora_payload(nombre="  "),
        headers=headers,
    )
    assert response.status_code == 422


async def test_crear_distribuidora_anonimo_401(client) -> None:
    response = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload()
    )
    assert response.status_code == 401


async def test_crear_distribuidora_como_mostrador_403(client) -> None:
    headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers
    )
    assert response.status_code == 403


# --- Obtener ---


async def test_obtener_distribuidora_por_id_200(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers
    )
    distribuidora_id = created.json()["id"]
    response = await client.get(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["id"] == distribuidora_id


async def test_obtener_distribuidora_como_mostrador_200(client) -> None:
    headers_duena = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers_duena
    )
    distribuidora_id = created.json()["id"]
    headers_mostrador = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.get(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}", headers=headers_mostrador
    )
    assert response.status_code == 200


async def test_obtener_distribuidora_id_inexistente_404(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.get(
        f"{DISTRIBUIDORAS_URL}/id-que-no-existe", headers=headers
    )
    assert response.status_code == 404


# --- Actualizar ---


async def test_actualizar_distribuidora_200(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers
    )
    distribuidora_id = created.json()["id"]
    response = await client.put(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}",
        json={"condiciones": "pago a 30 dias"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["condiciones"] == "pago a 30 dias"


async def test_actualizar_distribuidora_como_mostrador_403(client) -> None:
    headers_duena = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers_duena
    )
    distribuidora_id = created.json()["id"]
    headers_mostrador = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.put(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}",
        json={"condiciones": "x"},
        headers=headers_mostrador,
    )
    assert response.status_code == 403


# --- Eliminar (soft-delete) ---


async def test_eliminar_distribuidora_204_activo_false(
    client, db_session_factory
) -> None:
    from app.models import Distribuidora

    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers
    )
    distribuidora_id = created.json()["id"]
    response = await client.delete(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}", headers=headers
    )
    assert response.status_code == 204
    with db_session_factory() as session:
        distribuidora = session.get(Distribuidora, distribuidora_id)
        assert distribuidora is not None
        assert distribuidora.activo is False


# --- Listar paginado (TRIANGULATE 2.3) ---


async def test_listar_distribuidoras_paginado_200_con_metadata(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    for i in range(3):
        await client.post(
            DISTRIBUIDORAS_URL,
            json=_distribuidora_payload(nombre=f"Distri {i}"),
            headers=headers,
        )
    response = await client.get(
        f"{DISTRIBUIDORAS_URL}?page=1&page_size=20", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 1
    assert len(body["items"]) == 3


async def test_listar_distribuidoras_solo_activas(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        DISTRIBUIDORAS_URL,
        json=_distribuidora_payload(nombre="Activa"),
        headers=headers,
    )
    activa_id = created.json()["id"]
    created2 = await client.post(
        DISTRIBUIDORAS_URL,
        json=_distribuidora_payload(nombre="Borrada"),
        headers=headers,
    )
    borrada_id = created2.json()["id"]
    await client.delete(f"{DISTRIBUIDORAS_URL}/{borrada_id}", headers=headers)
    response = await client.get(DISTRIBUIDORAS_URL, headers=headers)
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert activa_id in ids
    assert borrada_id not in ids
    assert body["total"] == 1


async def test_actualizar_distribuidora_parcial_contacto_condiciones(
    client,
) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        DISTRIBUIDORAS_URL, json=_distribuidora_payload(), headers=headers
    )
    distribuidora_id = created.json()["id"]
    nombre_original = created.json()["nombre"]
    response = await client.put(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}",
        json={"contacto": "Ana 555-999", "condiciones": "contado"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contacto"] == "Ana 555-999"
    assert body["condiciones"] == "contado"
    assert body["nombre"] == nombre_original
