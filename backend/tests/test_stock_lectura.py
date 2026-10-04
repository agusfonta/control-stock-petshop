"""Lectura GET /api/stock con badge bajo_minimo (C-05 task 2.1, RED-first).

Cubre spec scenarios: alerta al llegar al minimo, sin alerta por encima,
filtro bajo_minimo=true, orden=rotacion por cobertura ascendente,
401 anonimo, 422 orden invalido. En RED fallan: el router no existe.
"""

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD
from tests.test_productos_crud import _login, _producto_payload

STOCK_URL = "/api/stock"


async def _crear(client, headers, **overrides):
    response = await client.post(
        "/api/productos", json=_producto_payload(**overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def test_badge_true_cuando_stock_igual_al_minimo(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(
        client, headers, sku="STK-EQ", stock_actual=5, stock_minimo=5
    )
    response = await client.get(STOCK_URL, headers=headers)
    assert response.status_code == 200
    items = {i["sku"]: i for i in response.json()["items"]}
    assert items["STK-EQ"]["bajo_minimo"] is True
    assert items["STK-EQ"]["stock_actual"] == 5
    assert items["STK-EQ"]["stock_minimo"] == creado["stock_minimo"]


async def test_badge_false_por_encima_del_minimo(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-OK", stock_actual=10, stock_minimo=2)
    response = await client.get(STOCK_URL, headers=headers)
    assert response.status_code == 200
    items = {i["sku"]: i for i in response.json()["items"]}
    assert items["STK-OK"]["bajo_minimo"] is False


async def test_filtro_solo_bajo_stock(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-BAJO", stock_actual=1, stock_minimo=5)
    await _crear(client, headers, sku="STK-ALTO", stock_actual=20, stock_minimo=5)
    response = await client.get(f"{STOCK_URL}?bajo_minimo=true", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["sku"] == "STK-BAJO"
    assert body["items"][0]["bajo_minimo"] is True


async def test_orden_rotacion_por_cobertura_ascendente(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-A", stock_actual=10, stock_minimo=2)
    await _crear(client, headers, sku="STK-B", stock_actual=1, stock_minimo=5)
    await _crear(client, headers, sku="STK-C", stock_actual=5, stock_minimo=5)
    response = await client.get(f"{STOCK_URL}?orden=rotacion", headers=headers)
    assert response.status_code == 200
    skus = [i["sku"] for i in response.json()["items"]]
    # Coberturas: B=-4, C=0, A=8 -> el mas negativo primero.
    assert skus == ["STK-B", "STK-C", "STK-A"]


async def test_lectura_anonima_401(client) -> None:
    response = await client.get(STOCK_URL)
    assert response.status_code == 401


async def test_orden_invalido_422(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.get(f"{STOCK_URL}?orden=invalido", headers=headers)
    assert response.status_code == 422
