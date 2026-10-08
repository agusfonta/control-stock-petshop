"""GET /api/stock/alertas (C-05, RED-first).

Cubre spec scenarios: resumen coincide con el filtro, vacio total=0 y
acceso anonimo rechazado.
"""

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD
from tests.test_productos_crud import _login, _producto_payload


async def _crear(client, headers, **overrides):
    response = await client.post(
        "/api/productos", json=_producto_payload(**overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def test_resumen_coincide_con_filtro(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-R1", stock_actual=1, stock_minimo=5)
    await _crear(client, headers, sku="STK-R2", stock_actual=5, stock_minimo=5)
    await _crear(client, headers, sku="STK-R3", stock_actual=0, stock_minimo=3)
    await _crear(client, headers, sku="STK-R4", stock_actual=20, stock_minimo=5)
    alertas = (await client.get("/api/stock/alertas", headers=headers)).json()
    filtrados = (
        await client.get("/api/stock?bajo_minimo=true", headers=headers)
    ).json()
    assert alertas["total_bajo_minimo"] == 3
    assert {i["sku"] for i in alertas["items"]} == {
        i["sku"] for i in filtrados["items"]
    } == {"STK-R1", "STK-R2", "STK-R3"}


async def test_sin_bajo_minimo_total_cero(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-R5", stock_actual=20, stock_minimo=5)
    response = await client.get("/api/stock/alertas", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_bajo_minimo"] == 0
    assert body["items"] == []


async def test_alertas_anonimo_401(client) -> None:
    response = await client.get("/api/stock/alertas")
    assert response.status_code == 401
