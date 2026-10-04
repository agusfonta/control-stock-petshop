"""Listas de precios por distribuidora via API (C-06 task 3.1, RED-first).

POST/GET/PUT/DELETE /api/distribuidoras/{id}/listas. Par unico
(distribuidora, producto): duplicado responde 409. Escritura solo duena.
"""

from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)

DISTRIBUIDORAS_URL = "/api/distribuidoras"
PRODUCTOS_URL = "/api/productos"


async def _login(client, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _crear_distribuidora(client, headers, nombre="Distri Sur") -> str:
    response = await client.post(
        DISTRIBUIDORAS_URL, json={"nombre": nombre}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _crear_producto(client, headers, sku="SKU-LP-001") -> str:
    response = await client.post(
        PRODUCTOS_URL,
        json={"sku": sku, "nombre": "Alimento Perro", "costo": 1000},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_agregar_costo_a_lista_201(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_id = await _crear_distribuidora(client, headers)
    producto_id = await _crear_producto(client, headers)
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": 800},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["distribuidora_id"] == distribuidora_id
    assert body["producto_id"] == producto_id
    assert body["costo"] == 800


async def test_agregar_costo_duplicado_409(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_id = await _crear_distribuidora(client, headers)
    producto_id = await _crear_producto(client, headers)
    await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": 800},
        headers=headers,
    )
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": 850},
        headers=headers,
    )
    assert response.status_code == 409


async def test_agregar_costo_cero_422(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_id = await _crear_distribuidora(client, headers)
    producto_id = await _crear_producto(client, headers)
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": 0},
        headers=headers,
    )
    assert response.status_code == 422


async def test_agregar_costo_producto_inexistente_404(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_id = await _crear_distribuidora(client, headers)
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": "producto-que-no-existe", "costo": 800},
        headers=headers,
    )
    assert response.status_code == 404


async def test_agregar_costo_distribuidora_inexistente_404(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    producto_id = await _crear_producto(client, headers)
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/distribuidora-que-no-existe/listas",
        json={"producto_id": producto_id, "costo": 800},
        headers=headers,
    )
    assert response.status_code == 404


async def test_actualizar_costo_lista_200(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_id = await _crear_distribuidora(client, headers)
    producto_id = await _crear_producto(client, headers)
    await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": 800},
        headers=headers,
    )
    response = await client.put(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas/{producto_id}",
        json={"costo": 850},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["costo"] == 850


async def test_quitar_de_lista_204_sin_afectar_producto(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_id = await _crear_distribuidora(client, headers)
    producto_id = await _crear_producto(client, headers)
    await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": 800},
        headers=headers,
    )
    response = await client.delete(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas/{producto_id}",
        headers=headers,
    )
    assert response.status_code == 204
    # El producto y la distribuidora siguen existiendo.
    assert (
        await client.get(f"{PRODUCTOS_URL}/{producto_id}", headers=headers)
    ).status_code == 200
    assert (
        await client.get(
            f"{DISTRIBUIDORAS_URL}/{distribuidora_id}", headers=headers
        )
    ).status_code == 200
    # La entrada ya no figura.
    listado = await client.get(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas", headers=headers
    )
    assert listado.status_code == 200
    assert listado.json() == []


async def test_escribir_lista_como_mostrador_403(client) -> None:
    headers_duena = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_id = await _crear_distribuidora(client, headers_duena)
    producto_id = await _crear_producto(client, headers_duena)
    headers_mostrador = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": 800},
        headers=headers_mostrador,
    )
    assert response.status_code == 403


async def test_mismo_producto_en_dos_distribuidoras_ok(client) -> None:
    """La unicidad es por par (distribuidora, producto), no global (3.3)."""
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    distribuidora_a = await _crear_distribuidora(client, headers, nombre="A")
    distribuidora_b = await _crear_distribuidora(client, headers, nombre="B")
    producto_id = await _crear_producto(client, headers)
    for distribuidora_id, costo in ((distribuidora_a, 800), (distribuidora_b, 1000)):
        response = await client.post(
            f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
            json={"producto_id": producto_id, "costo": costo},
            headers=headers,
        )
        assert response.status_code == 201
    listado_a = await client.get(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_a}/listas", headers=headers
    )
    listado_b = await client.get(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_b}/listas", headers=headers
    )
    assert [e["costo"] for e in listado_a.json()] == [800]
    assert [e["costo"] for e in listado_b.json()] == [1000]
