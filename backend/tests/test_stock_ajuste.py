"""Ajuste auditable POST /api/productos/{id}/ajustar (C-05 task 3.1, RED-first).

Cubre spec scenarios: ajuste positivo con movimiento, cantidad negativa,
403 mostrador, 401 anonimo, 422 motivo vacio, 422 stock negativo,
404 inexistente, PUT con stock -> 422 sin cambios, rollback si falla
el movimiento, payload malformado -> 422. En RED fallan: no existe
ni el endpoint ni services/stock.py.
"""

import pytest

from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)
from tests.test_productos_crud import _login, _producto_payload

PRODUCTOS_URL = "/api/productos"


async def _crear(client, headers, **overrides):
    response = await client.post(
        PRODUCTOS_URL, json=_producto_payload(**overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _movimientos_de(db_session_factory, producto_id: str) -> list:
    from app.models import MovimientoStock

    with db_session_factory() as session:
        return (
            session.query(MovimientoStock)
            .filter_by(producto_id=producto_id)
            .order_by(MovimientoStock.created_at.asc())
            .all()
        )


async def test_ajuste_positivo_genera_movimiento(client, db_session_factory) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, headers, sku="STK-AJ1", stock_actual=10)
    duena_id = (await client.get("/api/auth/me", headers=headers)).json()["id"]
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"cantidad_delta": 5, "motivo": "conteo fisico"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["producto"]["stock_actual"] == 15
    mov = body["movimiento"]
    assert mov["tipo"] == "ajuste"
    assert mov["cantidad"] == 5
    assert mov["stock_previo"] == 10
    assert mov["stock_nuevo"] == 15
    assert mov["motivo"] == "conteo fisico"
    assert mov["usuario_id"] == duena_id
    assert mov["producto_id"] == creado["id"]


async def test_ajuste_negativo_genera_movimiento(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, headers, sku="STK-AJ2", stock_actual=10)
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"cantidad_delta": -3, "motivo": "rotura"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["producto"]["stock_actual"] == 7
    assert body["movimiento"]["cantidad"] == -3
    assert body["movimiento"]["stock_previo"] == 10
    assert body["movimiento"]["stock_nuevo"] == 7


async def test_ajuste_como_mostrador_403_sin_cambios(
    client, db_session_factory
) -> None:
    duena = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, duena, sku="STK-AJ3", stock_actual=10)
    mostrador = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"cantidad_delta": 5, "motivo": "conteo fisico"},
        headers=mostrador,
    )
    assert response.status_code == 403
    assert (await client.get(f"{PRODUCTOS_URL}/{creado['id']}", headers=duena)).json()[
        "stock_actual"
    ] == 10
    assert _movimientos_de(db_session_factory, creado["id"]) == []


async def test_ajuste_anonimo_401(client) -> None:
    response = await client.post(
        f"{PRODUCTOS_URL}/inexistente/ajustar",
        json={"cantidad_delta": 5, "motivo": "conteo fisico"},
    )
    assert response.status_code == 401


async def test_ajuste_motivo_vacio_422_sin_cambios(
    client, db_session_factory
) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, headers, sku="STK-AJ4", stock_actual=10)
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"cantidad_delta": 5, "motivo": "  "},
        headers=headers,
    )
    assert response.status_code == 422
    assert (await client.get(f"{PRODUCTOS_URL}/{creado['id']}", headers=headers)).json()[
        "stock_actual"
    ] == 10
    assert _movimientos_de(db_session_factory, creado["id"]) == []


async def test_ajuste_stock_negativo_422_sin_cambios(
    client, db_session_factory
) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, headers, sku="STK-AJ5", stock_actual=2)
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"cantidad_delta": -5, "motivo": "error"},
        headers=headers,
    )
    assert response.status_code == 422
    assert (await client.get(f"{PRODUCTOS_URL}/{creado['id']}", headers=headers)).json()[
        "stock_actual"
    ] == 2
    assert _movimientos_de(db_session_factory, creado["id"]) == []


async def test_ajuste_producto_inexistente_404_sin_movimiento(
    client, db_session_factory
) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    response = await client.post(
        f"{PRODUCTOS_URL}/no-existe/ajustar",
        json={"cantidad_delta": 5, "motivo": "conteo fisico"},
        headers=headers,
    )
    assert response.status_code == 404
    assert _movimientos_de(db_session_factory, "no-existe") == []


async def test_put_con_stock_422_sin_cambios(client, db_session_factory) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, headers, sku="STK-AJ6", stock_actual=10)
    response = await client.put(
        f"{PRODUCTOS_URL}/{creado['id']}",
        json={"nombre": "Nuevo nombre", "stock_actual": 99},
        headers=headers,
    )
    assert response.status_code == 422
    body = (await client.get(f"{PRODUCTOS_URL}/{creado['id']}", headers=headers)).json()
    assert body["stock_actual"] == 10
    assert body["nombre"] != "Nuevo nombre"
    assert _movimientos_de(db_session_factory, creado["id"]) == []


async def test_fallo_movimiento_revierte_stock(client, monkeypatch) -> None:
    from sqlalchemy.orm import Session

    from app.models import MovimientoStock

    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, headers, sku="STK-AJ7", stock_actual=10)
    original_add = Session.add

    def _add_falla(self, instance, *args, **kwargs):
        if isinstance(instance, MovimientoStock):
            raise RuntimeError("falla simulada del ledger")
        return original_add(self, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "add", _add_falla)
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"cantidad_delta": 5, "motivo": "conteo fisico"},
        headers=headers,
    )
    assert response.status_code == 500
    monkeypatch.undo()
    body = (await client.get(f"{PRODUCTOS_URL}/{creado['id']}", headers=headers)).json()
    assert body["stock_actual"] == 10


async def test_ajuste_payload_malformado_422(client, db_session_factory) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    creado = await _crear(client, headers, sku="STK-AJ8", stock_actual=10)
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"motivo": "sin delta"},
        headers=headers,
    )
    assert response.status_code == 422
    response = await client.post(
        f"{PRODUCTOS_URL}/{creado['id']}/ajustar",
        json={"cantidad_delta": "mucho", "motivo": "tipo invalido"},
        headers=headers,
    )
    assert response.status_code == 422
    assert _movimientos_de(db_session_factory, creado["id"]) == []
