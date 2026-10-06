"""Historial de ventas por cliente (C-10 task 10.1, RED-first, capability clientes).

GET /api/clientes/{id}/ventas (D12/D15): confirmadas y anuladas del cliente
(nunca borradores), created_at desc, paginado como el resto; el mostrador ve
solo las que el registro; el cliente dado de baja conserva su historial.
En RED fallan: el endpoint no existe (404/405).
"""

from datetime import datetime, timezone

import pytest

from tests.ventas_helpers import (
    CLIENTES_URL,
    crear_cliente,
    crear_producto,
    crear_venta,
    login_duena,
    login_mostrador,
    pago,
    post_anular,
    usuario_id,
    venta_confirmada,
)


def _historial_url(cliente_id: str) -> str:
    return f"{CLIENTES_URL}/{cliente_id}/ventas"


async def _producto(client, duena):
    return await crear_producto(client, duena, sku="HI-A", costo=1000, margen_pct=0.5, stock_actual=100)


async def _confirmada(client, headers, producto_id, **kwargs):
    return await venta_confirmada(client, headers, [(producto_id, 1)], [pago("efectivo", 1500)], **kwargs)


def _fijar_created_at(db_session_factory, venta_id: str, momento: datetime) -> None:
    from app.models import Venta

    with db_session_factory() as session:
        session.get(Venta, venta_id).created_at = momento
        session.commit()


def _ids(response) -> list[str]:
    return [item["id"] for item in response.json()["items"]]


async def test_historial_trae_confirmada_y_anulada_sin_borrador_mas_reciente_primero(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    cliente_id = await crear_cliente(client, duena)
    confirmada = await _confirmada(client, duena, a, cliente_id=cliente_id)
    anulada = await _confirmada(client, duena, a, cliente_id=cliente_id)
    await post_anular(client, duena, anulada["id"])
    await crear_venta(client, duena, [(a, 1)], cliente_id=cliente_id)  # borrador
    _fijar_created_at(db_session_factory, confirmada["id"], datetime(2026, 5, 1, 12, tzinfo=timezone.utc))
    _fijar_created_at(db_session_factory, anulada["id"], datetime(2026, 5, 2, 12, tzinfo=timezone.utc))
    response = await client.get(_historial_url(cliente_id), headers=duena)
    assert response.status_code == 200
    body = response.json()
    assert _ids(response) == [anulada["id"], confirmada["id"]]
    assert [i["estado"] for i in body["items"]] == ["anulada", "confirmada"]
    assert body["total"] == 2
    item = body["items"][1]
    assert item["total"] == 1500
    assert item["usuario_id"] == await usuario_id(client, duena)
    assert item["created_at"] is not None and item["confirmada_at"] is not None
    assert set(item) == {
        "id", "estado", "cliente_id", "usuario_id", "total",
        "created_at", "confirmada_at", "anulada_at",
    }  # fmt: skip


async def test_historial_no_mezcla_ventas_de_otros_clientes(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    ana = await crear_cliente(client, duena, "Ana")
    beto = await crear_cliente(client, duena, "Beto")
    de_ana = await _confirmada(client, duena, a, cliente_id=ana)
    await _confirmada(client, duena, a, cliente_id=beto)
    await _confirmada(client, duena, a)  # sin cliente
    response = await client.get(_historial_url(ana), headers=duena)
    assert _ids(response) == [de_ana["id"]]


async def test_cliente_sin_ventas_200_lista_vacia(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    cliente_id = await crear_cliente(client, duena)
    for headers in (duena, mostrador):
        response = await client.get(_historial_url(cliente_id), headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["items"], body["total_pages"]) == (0, [], 0)


async def test_mostrador_ve_solo_sus_ventas_del_cliente(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena)
    cliente_id = await crear_cliente(client, duena)
    await _confirmada(client, duena, a, cliente_id=cliente_id)
    propia = await _confirmada(client, mostrador, a, cliente_id=cliente_id)
    response = await client.get(_historial_url(cliente_id), headers=mostrador)
    assert response.status_code == 200
    assert _ids(response) == [propia["id"]]
    assert response.json()["total"] == 1
    # La duena ve las dos.
    assert (await client.get(_historial_url(cliente_id), headers=duena)).json()["total"] == 2


async def test_cliente_dado_de_baja_conserva_su_historial(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    cliente_id = await crear_cliente(client, duena)
    venta = await _confirmada(client, duena, a, cliente_id=cliente_id)
    assert (await client.delete(f"{CLIENTES_URL}/{cliente_id}", headers=duena)).status_code == 204
    response = await client.get(_historial_url(cliente_id), headers=duena)
    assert response.status_code == 200
    assert _ids(response) == [venta["id"]]


async def test_historial_de_cliente_inexistente_404(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    for headers in (duena, mostrador):
        response = await client.get(_historial_url("no-existe"), headers=headers)
        assert response.status_code == 404


async def test_historial_sin_autenticacion_401(client) -> None:
    duena = await login_duena(client)
    cliente_id = await crear_cliente(client, duena)
    assert (await client.get(_historial_url(cliente_id))).status_code == 401


async def test_historial_pagina_y_valida_page_size(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    cliente_id = await crear_cliente(client, duena)
    ventas = [await _confirmada(client, duena, a, cliente_id=cliente_id) for _ in range(3)]
    for indice, venta in enumerate(ventas):
        _fijar_created_at(db_session_factory, venta["id"], datetime(2026, 5, 1 + indice, 12, tzinfo=timezone.utc))
    primera = await client.get(_historial_url(cliente_id), params={"page_size": 2}, headers=duena)
    segunda = await client.get(_historial_url(cliente_id), params={"page_size": 2, "page": 2}, headers=duena)
    cuerpo = primera.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"], cuerpo["total_pages"]) == (3, 1, 2, 2)
    assert _ids(primera) == [ventas[2]["id"], ventas[1]["id"]]
    assert _ids(segunda) == [ventas[0]["id"]]
    for params in ({"page_size": 101}, {"page": 0}):
        assert (await client.get(_historial_url(cliente_id), params=params, headers=duena)).status_code == 422


@pytest.mark.parametrize("ruta", ["/buscar?q=ana", ""])
async def test_las_rutas_de_clientes_existentes_siguen_resolviendo(client, ruta) -> None:
    """/buscar no se interpreta como id y el listado sigue en pie (D7 de C-09)."""
    duena = await login_duena(client)
    await crear_cliente(client, duena, "Ana")
    response = await client.get(f"{CLIENTES_URL}{ruta}", headers=duena)
    assert response.status_code == 200
    assert response.json()["total"] == 1
