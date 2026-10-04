"""Comparar costos por distribuidora (C-06 task 4.1, RED-first).

GET /api/distribuidoras/comparar?producto_id=: costos por distribuidora
activa ordenados por costo ASC, cada uno con precio_sugerido =
costo x (1 + margen_pct) recalculado (RN-PR-01/RN-PR-03). Solo lectura.
"""

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD

DISTRIBUIDORAS_URL = "/api/distribuidoras"
PRODUCTOS_URL = "/api/productos"
COMPARAR_URL = "/api/distribuidoras/comparar"


async def _login(client, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _crear_distribuidora(client, headers, nombre="Distri") -> str:
    response = await client.post(
        DISTRIBUIDORAS_URL, json={"nombre": nombre}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _crear_producto(client, headers, sku, margen_pct=0.5) -> str:
    response = await client.post(
        PRODUCTOS_URL,
        json={
            "sku": sku,
            "nombre": "Alimento Perro",
            "costo": 1000,
            "margen_pct": margen_pct,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _cargar_costo(client, headers, distribuidora_id, producto_id, costo):
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": costo},
        headers=headers,
    )
    assert response.status_code == 201


async def test_comparar_dos_origenes_ordenados_con_sugerido(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    producto_id = await _crear_producto(client, headers, sku="SKU-CMP-001")
    distri_b = await _crear_distribuidora(client, headers, nombre="B")
    distri_a = await _crear_distribuidora(client, headers, nombre="A")
    await _cargar_costo(client, headers, distri_b, producto_id, 1000)
    await _cargar_costo(client, headers, distri_a, producto_id, 800)
    response = await client.get(
        f"{COMPARAR_URL}?producto_id={producto_id}", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["producto_id"] == producto_id
    assert len(body["filas"]) == 2
    assert body["filas"][0]["costo"] == 800
    assert body["filas"][0]["precio_sugerido"] == 1200
    assert body["filas"][1]["costo"] == 1000
    assert body["filas"][1]["precio_sugerido"] == 1500


async def test_comparar_refleja_cambio_de_costo(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    producto_id = await _crear_producto(client, headers, sku="SKU-CMP-002")
    distribuidora_id = await _crear_distribuidora(client, headers)
    await _cargar_costo(client, headers, distribuidora_id, producto_id, 800)
    await client.put(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas/{producto_id}",
        json={"costo": 900},
        headers=headers,
    )
    response = await client.get(
        f"{COMPARAR_URL}?producto_id={producto_id}", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["filas"][0]["precio_sugerido"] == 1350


async def test_comparar_producto_inexistente_404(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.get(
        f"{COMPARAR_URL}?producto_id=no-existe", headers=headers
    )
    assert response.status_code == 404


async def test_comparar_sin_producto_id_422(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.get(COMPARAR_URL, headers=headers)
    assert response.status_code == 422


async def test_comparar_producto_sin_listas_vacio_200(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    producto_id = await _crear_producto(client, headers, sku="SKU-CMP-003")
    response = await client.get(
        f"{COMPARAR_URL}?producto_id={producto_id}", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["filas"] == []


async def test_comparar_sin_auth_401(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    producto_id = await _crear_producto(client, headers, sku="SKU-CMP-004")
    response = await client.get(f"{COMPARAR_URL}?producto_id={producto_id}")
    assert response.status_code == 401


async def test_comparar_sugerido_iguala_precio_venta_con_mismo_costo(
    client,
) -> None:
    """Si el costo de lista iguala al costo base, el sugerido de comparar
    coincide con el precio_venta del producto (una sola formula, D4)."""
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    producto_id = await _crear_producto(client, headers, sku="SKU-CMP-005")
    producto = (
        await client.get(f"{PRODUCTOS_URL}/{producto_id}", headers=headers)
    ).json()
    distribuidora_id = await _crear_distribuidora(client, headers)
    await _cargar_costo(
        client, headers, distribuidora_id, producto_id, producto["costo"]
    )
    response = await client.get(
        f"{COMPARAR_URL}?producto_id={producto_id}", headers=headers
    )
    assert response.status_code == 200
    fila = response.json()["filas"][0]
    assert fila["precio_sugerido"] == producto["precio_venta"]


async def test_comparar_excluye_distribuidora_inactiva(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    producto_id = await _crear_producto(client, headers, sku="SKU-CMP-006")
    activa_id = await _crear_distribuidora(client, headers, nombre="Activa")
    inactiva_id = await _crear_distribuidora(client, headers, nombre="Baja")
    await _cargar_costo(client, headers, activa_id, producto_id, 1000)
    await _cargar_costo(client, headers, inactiva_id, producto_id, 500)
    await client.delete(
        f"{DISTRIBUIDORAS_URL}/{inactiva_id}", headers=headers
    )
    response = await client.get(
        f"{COMPARAR_URL}?producto_id={producto_id}", headers=headers
    )
    assert response.status_code == 200
    filas = response.json()["filas"]
    assert len(filas) == 1
    assert filas[0]["distribuidora_id"] == activa_id
