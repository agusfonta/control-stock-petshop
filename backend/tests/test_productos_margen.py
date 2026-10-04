"""Configuracion de margen y stock minimo (C-04 task 5.1, RED-first).

PATCH /api/productos/{id}/margen-minimo — solo duena (RN-PR-02, RN-ST-02).
Al cambiar margen_pct, precio_venta se recalcula (RN-PR-01).
"""

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD

PRODUCTOS_URL = "/api/productos"


def _producto_payload(**overrides):
    payload = {
        "sku": "SKU-001",
        "nombre": "Alimento Perro 20kg",
        "costo": 1000,
        "margen_pct": 0.5,
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


async def _crear(client, headers, **overrides):
    response = await client.post(
        PRODUCTOS_URL, json=_producto_payload(**overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


# --- Dueña actualiza margen ---


async def test_duena_actualiza_margen_200_precio_recalculado(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await _crear(client, headers)
    producto_id = created["id"]
    response = await client.patch(
        f"{PRODUCTOS_URL}/{producto_id}/margen-minimo",
        json={"margen_pct": 0.35},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["margen_pct"] == 0.35
    assert body["precio_venta"] == 1350  # 1000 * (1 + 0.35)


# --- Dueña actualiza stock mínimo ---


async def test_duena_actualiza_stock_minimo_200(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await _crear(client, headers)
    producto_id = created["id"]
    response = await client.patch(
        f"{PRODUCTOS_URL}/{producto_id}/margen-minimo",
        json={"stock_minimo": 5},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stock_minimo"] == 5


# --- Dueña actualiza ambos ---


async def test_duena_actualiza_margen_y_stock_minimo_200(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await _crear(client, headers)
    producto_id = created["id"]
    response = await client.patch(
        f"{PRODUCTOS_URL}/{producto_id}/margen-minimo",
        json={"margen_pct": 0.40, "stock_minimo": 10},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["margen_pct"] == 0.40
    assert body["stock_minimo"] == 10
    assert body["precio_venta"] == 1400  # 1000 * (1 + 0.40)


# --- Mostrador intenta actualizar ---


async def test_mostrador_intenta_actualizar_margen_403(client) -> None:
    headers_duena = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await _crear(client, headers_duena)
    producto_id = created["id"]
    headers_mostrador = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.patch(
        f"{PRODUCTOS_URL}/{producto_id}/margen-minimo",
        json={"margen_pct": 0.35},
        headers=headers_mostrador,
    )
    assert response.status_code == 403


# --- Margen negativo rechazado ---


async def test_margen_negativo_422(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await _crear(client, headers)
    producto_id = created["id"]
    response = await client.patch(
        f"{PRODUCTOS_URL}/{producto_id}/margen-minimo",
        json={"margen_pct": -0.5},
        headers=headers,
    )
    assert response.status_code == 422


# --- Stock mínimo negativo rechazado ---


async def test_stock_minimo_negativo_422(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await _crear(client, headers)
    producto_id = created["id"]
    response = await client.patch(
        f"{PRODUCTOS_URL}/{producto_id}/margen-minimo",
        json={"stock_minimo": -1},
        headers=headers,
    )
    assert response.status_code == 422


# --- Sin auth ---


async def test_margen_minimo_sin_auth_401(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    created = await _crear(client, headers)
    producto_id = created["id"]
    response = await client.patch(
        f"{PRODUCTOS_URL}/{producto_id}/margen-minimo",
        json={"margen_pct": 0.35},
    )
    assert response.status_code == 401
