"""CRUD de productos via API (C-04 task 3.1, RED-first).

Cada test debe fallar en RED (el router /api/productos no existe aun).
Autenticacion via login de seed_users (conftest). Escritura = duena,
lectura = cualquier usuario activo.
"""


from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)

PRODUCTOS_URL = "/api/productos"


def _producto_payload(**overrides):
    payload = {
        "sku": "SKU-001",
        "nombre": "Alimento Perro 20kg",
        "marca": "Marca",
        "categoria": "alimentos",
        "unidad": "bolsa",
        "costo": 1000,
        "margen_pct": 0.5,
        "stock_actual": 10,
        "stock_minimo": 2,
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


# --- Crear ---


async def test_crear_producto_201_con_precio_venta_calculado(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "SKU-001"
    assert body["precio_venta"] == 1500  # 1000 * (1 + 0.5)
    assert body["activo"] is True
    assert body["id"]


async def test_crear_producto_sin_auth_401(client) -> None:
    response = await client.post(PRODUCTOS_URL, json=_producto_payload())
    assert response.status_code == 401


async def test_crear_producto_como_mostrador_403(client) -> None:
    headers = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers
    )
    assert response.status_code == 403


async def test_crear_producto_sku_duplicado_409(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await client.post(PRODUCTOS_URL, json=_producto_payload(), headers=headers)
    response = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers
    )
    assert response.status_code == 409


async def test_crear_producto_payload_malformado_422(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.post(
        PRODUCTOS_URL, json=_producto_payload(costo=-100), headers=headers
    )
    assert response.status_code == 422


# --- Obtener por ID ---


async def test_obtener_producto_por_id_200(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers
    )
    producto_id = created.json()["id"]
    response = await client.get(f"{PRODUCTOS_URL}/{producto_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == producto_id
    assert body["sku"] == "SKU-001"


async def test_obtener_producto_por_id_sin_auth_401(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers
    )
    producto_id = created.json()["id"]
    response = await client.get(f"{PRODUCTOS_URL}/{producto_id}")
    assert response.status_code == 401


# --- Actualizar ---


async def test_actualizar_producto_200_precio_recalculado(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers
    )
    producto_id = created.json()["id"]
    response = await client.put(
        f"{PRODUCTOS_URL}/{producto_id}",
        json={"costo": 2000, "margen_pct": 0.25},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["costo"] == 2000
    assert body["margen_pct"] == 0.25
    assert body["precio_venta"] == 2500  # 2000 * (1 + 0.25)


async def test_actualizar_producto_como_mostrador_403(client) -> None:
    headers_duena = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers_duena
    )
    producto_id = created.json()["id"]
    headers_mostrador = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.put(
        f"{PRODUCTOS_URL}/{producto_id}",
        json={"costo": 2000},
        headers=headers_mostrador,
    )
    assert response.status_code == 403


# --- Eliminar (soft-delete) ---


async def test_eliminar_producto_204_activo_false(
    client, db_session_factory
) -> None:
    from app.models import Producto

    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers
    )
    producto_id = created.json()["id"]
    response = await client.delete(
        f"{PRODUCTOS_URL}/{producto_id}", headers=headers
    )
    assert response.status_code == 204
    with db_session_factory() as session:
        producto = session.get(Producto, producto_id)
        assert producto is not None
        assert producto.activo is False


async def test_eliminar_producto_como_mostrador_403(client) -> None:
    headers_duena = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        PRODUCTOS_URL, json=_producto_payload(), headers=headers_duena
    )
    producto_id = created.json()["id"]
    headers_mostrador = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.delete(
        f"{PRODUCTOS_URL}/{producto_id}", headers=headers_mostrador
    )
    assert response.status_code == 403


# --- Listar paginado ---


async def test_listar_productos_paginado_200_con_metadata(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    for i in range(3):
        await client.post(
            PRODUCTOS_URL, json=_producto_payload(sku=f"SKU-L-{i}"), headers=headers
        )
    response = await client.get(
        f"{PRODUCTOS_URL}?page=1&page_size=20", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 1
    assert len(body["items"]) == 3


async def test_listar_productos_sin_auth_401(client) -> None:
    response = await client.get(PRODUCTOS_URL)
    assert response.status_code == 401


async def test_listar_productos_filtra_inactivos(
    client, db_session_factory
) -> None:

    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await client.post(
        PRODUCTOS_URL, json=_producto_payload(sku="SKU-ACTIVO"), headers=headers
    )
    activo_id = created.json()["id"]
    created2 = await client.post(
        PRODUCTOS_URL, json=_producto_payload(sku="SKU-BORRADO"), headers=headers
    )
    borrado_id = created2.json()["id"]
    await client.delete(f"{PRODUCTOS_URL}/{borrado_id}", headers=headers)
    response = await client.get(PRODUCTOS_URL, headers=headers)
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert activo_id in ids
    assert borrado_id not in ids
    assert body["total"] == 1
