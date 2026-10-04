"""Busqueda de productos por SKU exacto o nombre parcial (C-04 task 4.1, RED-first).

GET /api/productos/buscar?q= usa OR(sku == q, nombre ILIKE %q%) con paginado.
"""

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD

BUSCAR_URL = "/api/productos/buscar"


def _producto_payload(**overrides):
    payload = {
        "sku": "SKU-001",
        "nombre": "Alimento Perro 20kg",
        "costo": 1000,
        "margen_pct": 0.5,
    }
    payload.update(overrides)
    return payload


async def _login(client, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _crear(client, headers, **overrides):
    response = await client.post(
        "/api/productos", json=_producto_payload(**overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


# --- Búsqueda por SKU exacto ---


async def test_buscar_por_sku_exacto(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="SKU-BUSQ", nombre="Alimento Perro")
    user_headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.get(f"{BUSCAR_URL}?q=SKU-BUSQ", headers=user_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["sku"] == "SKU-BUSQ"


# --- Búsqueda por nombre parcial ---


async def test_buscar_por_nombre_parcial(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="SKU-P1", nombre="Alimento Perro 20kg")
    await _crear(client, headers, sku="SKU-P2", nombre="Alimento Gato 10kg")
    await _crear(client, headers, sku="SKU-P3", nombre="Juguete Pelota")
    user_headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.get(f"{BUSCAR_URL}?q=Alimento", headers=user_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    skus = {item["sku"] for item in body["items"]}
    assert skus == {"SKU-P1", "SKU-P2"}


async def test_buscar_nombre_parcial_case_insensitive(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="SKU-CI", nombre="Alimento Perro")
    user_headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.get(f"{BUSCAR_URL}?q=alimento", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


# --- Búsqueda sin resultados ---


async def test_buscar_sin_resultados_lista_vacia(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="SKU-OK", nombre="Alimento Perro")
    user_headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.get(
        f"{BUSCAR_URL}?q=ZZZ-NO-EXISTE", headers=user_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["total_pages"] == 0


# --- Búsqueda sin query param ---


async def test_buscar_sin_query_param_422(client) -> None:
    user_headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.get(BUSCAR_URL, headers=user_headers)
    assert response.status_code == 422


async def test_buscar_sin_auth_401(client) -> None:
    response = await client.get(f"{BUSCAR_URL}?q=algo")
    assert response.status_code == 401


# --- Búsqueda paginada ---


async def test_buscar_paginado(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    for i in range(3):
        await _crear(
            client, headers, sku=f"SKU-PAG-{i}", nombre=f"Alimento {i}"
        )
    user_headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.get(
        f"{BUSCAR_URL}?q=Alimento&page=1&page_size=2", headers=user_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2
