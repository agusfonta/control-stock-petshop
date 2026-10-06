"""Lecturas de ventas con propiedad por vendedor (C-10 task 9.1, RED-first).

GET /api/ventas/{id} y GET /api/ventas (D12/D15): el mostrador ve solo sus
ventas (ajena => 404 en el detalle, listado siempre restringido), la duena
ve todas y filtra por usuario; el listado excluye borradores por defecto,
pagina 20/100, ordena por created_at desc y acepta desde/hasta con zona
(intervalo [desde, hasta)). En RED fallan: el detalle no restringe por
propiedad y GET /api/ventas no existe (405).
"""

from datetime import datetime, timezone

import pytest

from tests.ventas_helpers import (
    VENTAS_URL,
    clave_nueva,
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


async def _producto(client, duena, sku="LE-A", stock=100):
    return await crear_producto(client, duena, sku=sku, costo=1000, margen_pct=0.5, stock_actual=stock)


async def _confirmada(client, headers, producto_id, cantidad=1, **kwargs):
    return await venta_confirmada(
        client, headers, [(producto_id, cantidad)], [pago("efectivo", 1500 * cantidad)], **kwargs
    )


def _fijar_created_at(db_session_factory, venta_id: str, momento: datetime) -> None:
    from app.models import Venta

    with db_session_factory() as session:
        session.get(Venta, venta_id).created_at = momento
        session.commit()


def _utc(*partes) -> datetime:
    return datetime(*partes, tzinfo=timezone.utc)


async def _listar(client, headers, **params):
    return await client.get(VENTAS_URL, params=params, headers=headers)


def _ids(response) -> list[str]:
    return [item["id"] for item in response.json()["items"]]


# --- Detalle ---


async def test_mostrador_ve_el_detalle_de_su_venta_con_lineas_y_pagos(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena)
    venta = await _confirmada(client, mostrador, a, cantidad=2)
    response = await client.get(f"{VENTAS_URL}/{venta['id']}", headers=mostrador)
    assert response.status_code == 200
    body = response.json()
    assert body["estado"] == "confirmada"
    assert body["total"] == 3000
    assert body["usuario_id"] == await usuario_id(client, mostrador)
    (linea,) = body["lineas"]
    assert (linea["producto_id"], linea["cantidad"]) == (a, 2)
    assert linea["producto_nombre"] == "Producto LE-A"
    assert (linea["precio_unit"], linea["subtotal"]) == (1500, 3000)
    assert [(p["metodo"], p["monto"]) for p in body["pagos"]] == [("efectivo", 3000)]


async def test_detalle_ajeno_404_para_mostrador_y_200_para_duena(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena)
    de_duena = await _confirmada(client, duena, a)
    de_mostrador = await _confirmada(client, mostrador, a)
    ajena = await client.get(f"{VENTAS_URL}/{de_duena['id']}", headers=mostrador)
    assert ajena.status_code == 404
    propia = await client.get(f"{VENTAS_URL}/{de_mostrador['id']}", headers=duena)
    assert propia.status_code == 200
    assert propia.json()["id"] == de_mostrador["id"]


async def test_detalle_de_borrador_ajeno_tambien_404_para_mostrador(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena)
    borrador = await crear_venta(client, duena, [(a, 1)])
    assert (await client.get(f"{VENTAS_URL}/{borrador['id']}", headers=mostrador)).status_code == 404


async def test_detalle_inexistente_404(client) -> None:
    duena = await login_duena(client)
    assert (await client.get(f"{VENTAS_URL}/no-existe", headers=duena)).status_code == 404


async def test_lectura_anonima_401_en_listado_y_detalle(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    venta = await _confirmada(client, duena, a)
    assert (await client.get(VENTAS_URL)).status_code == 401
    assert (await client.get(f"{VENTAS_URL}/{venta['id']}")).status_code == 401


# --- Listado: propiedad ---


async def test_listado_del_mostrador_solo_trae_sus_ventas_aun_con_usuario_id_de_otro(
    client,
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena)
    de_duena = await _confirmada(client, duena, a)
    de_mostrador = await _confirmada(client, mostrador, a)
    sin_filtro = await _listar(client, mostrador)
    assert sin_filtro.status_code == 200
    assert _ids(sin_filtro) == [de_mostrador["id"]]
    ajeno = await _listar(client, mostrador, usuario_id=await usuario_id(client, duena))
    assert ajeno.status_code == 200
    assert ajeno.json()["items"] == [] and ajeno.json()["total"] == 0
    propio = await _listar(client, mostrador, usuario_id=await usuario_id(client, mostrador))
    assert _ids(propio) == [de_mostrador["id"]]
    assert de_duena["id"] not in _ids(sin_filtro)


async def test_duena_lista_todas_y_filtra_por_usuario_id(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena)
    de_duena = await _confirmada(client, duena, a)
    de_mostrador = await _confirmada(client, mostrador, a)
    todas = await _listar(client, duena)
    assert sorted(_ids(todas)) == sorted([de_duena["id"], de_mostrador["id"]])
    assert todas.json()["total"] == 2
    solo_mostrador = await _listar(client, duena, usuario_id=await usuario_id(client, mostrador))
    assert _ids(solo_mostrador) == [de_mostrador["id"]]


async def test_duena_filtra_por_cliente_id(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    cliente_id = await crear_cliente(client, duena)
    con_cliente = await _confirmada(client, duena, a, cliente_id=cliente_id)
    await _confirmada(client, duena, a)
    response = await _listar(client, duena, cliente_id=cliente_id)
    assert _ids(response) == [con_cliente["id"]]


# --- Listado: estado ---


async def test_listado_por_defecto_excluye_borradores(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    await crear_venta(client, duena, [(a, 1)])  # borrador
    confirmada = await _confirmada(client, duena, a)
    anulada = await _confirmada(client, duena, a)
    await post_anular(client, duena, anulada["id"])
    response = await _listar(client, duena)
    assert sorted(_ids(response)) == sorted([confirmada["id"], anulada["id"]])
    assert {i["estado"] for i in response.json()["items"]} == {"confirmada", "anulada"}
    assert response.json()["total"] == 2


async def test_listado_con_estado_explicito(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    borrador = await crear_venta(client, duena, [(a, 1)])
    confirmada = await _confirmada(client, duena, a)
    assert _ids(await _listar(client, duena, estado="borrador")) == [borrador["id"]]
    assert _ids(await _listar(client, duena, estado="confirmada")) == [confirmada["id"]]
    assert (await _listar(client, duena, estado="anulada")).json()["items"] == []


async def test_items_del_listado_son_resumenes_sin_lineas(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    venta = await _confirmada(client, duena, a, cantidad=2)
    (item,) = (await _listar(client, duena)).json()["items"]
    assert set(item) == {
        "id", "estado", "cliente_id", "usuario_id", "total",
        "created_at", "confirmada_at", "anulada_at",
    }  # fmt: skip
    assert (item["id"], item["total"], item["estado"]) == (venta["id"], 3000, "confirmada")


# --- Listado: periodo [desde, hasta) con zona ---


async def test_duena_lista_confirmadas_de_un_dia_con_intervalo_semiabierto(
    client, db_session_factory
) -> None:
    """Dia local Argentina (UTC-3) del 2026-10-05: [03:00Z, 03:00Z del dia 6)."""
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena)
    antes = await _confirmada(client, duena, a)  # 2026-10-04 23:59:59 local
    borde_inicio = await _confirmada(client, mostrador, a)  # 00:00:00 local
    fin_del_dia = await _confirmada(client, duena, a)  # 23:59:59 local
    borde_hasta = await _confirmada(client, duena, a)  # 00:00:00 del dia 6
    for venta, momento in [
        (antes, _utc(2026, 10, 5, 2, 59, 59)),
        (borde_inicio, _utc(2026, 10, 5, 3, 0, 0)),
        (fin_del_dia, _utc(2026, 10, 6, 2, 59, 59)),
        (borde_hasta, _utc(2026, 10, 6, 3, 0, 0)),
    ]:
        _fijar_created_at(db_session_factory, venta["id"], momento)
    response = await _listar(
        client,
        duena,
        estado="confirmada",
        desde="2026-10-05T00:00:00-03:00",
        hasta="2026-10-06T00:00:00-03:00",
    )
    assert response.status_code == 200
    assert _ids(response) == [fin_del_dia["id"], borde_inicio["id"]]  # created_at desc
    assert response.json()["total"] == 2


async def test_desde_y_hasta_se_pueden_usar_por_separado(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    vieja = await _confirmada(client, duena, a)
    nueva = await _confirmada(client, duena, a)
    _fijar_created_at(db_session_factory, vieja["id"], _utc(2026, 1, 1, 12))
    _fijar_created_at(db_session_factory, nueva["id"], _utc(2026, 6, 1, 12))
    solo_desde = await _listar(client, duena, desde="2026-03-01T00:00:00Z")
    solo_hasta = await _listar(client, duena, hasta="2026-03-01T00:00:00Z")
    assert _ids(solo_desde) == [nueva["id"]]
    assert _ids(solo_hasta) == [vieja["id"]]


# --- Listado: orden y paginacion ---


async def test_listado_ordenado_por_creacion_descendente_con_metadata_de_paginacion(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    ventas = [await _confirmada(client, duena, a) for _ in range(3)]
    for indice, venta in enumerate(ventas):
        _fijar_created_at(db_session_factory, venta["id"], _utc(2026, 5, 1 + indice, 12))
    primera = await _listar(client, duena, page_size=2)
    segunda = await _listar(client, duena, page_size=2, page=2)
    cuerpo = primera.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"], cuerpo["total_pages"]) == (3, 1, 2, 2)
    assert _ids(primera) == [ventas[2]["id"], ventas[1]["id"]]
    assert _ids(segunda) == [ventas[0]["id"]]
    assert segunda.json()["page"] == 2


async def test_listado_vacio_tiene_metadata_en_cero(client) -> None:
    duena = await login_duena(client)
    cuerpo = (await _listar(client, duena)).json()
    assert (cuerpo["total"], cuerpo["total_pages"], cuerpo["items"]) == (0, 0, [])
    assert (cuerpo["page"], cuerpo["page_size"]) == (1, 20)


# --- Listado: filtros invalidos ---


@pytest.mark.parametrize(
    "params",
    [
        {"estado": "pagada"},
        {"desde": "2026-10-05T00:00:00"},
        {"hasta": "2026-10-05T00:00:00"},
        {"desde": "ayer"},
        {"page_size": 101},
        {"page": 0},
    ],
)
async def test_filtros_invalidos_422(client, params) -> None:
    duena = await login_duena(client)
    assert (await _listar(client, duena, **params)).status_code == 422
    mostrador = await login_mostrador(client)
    assert (await _listar(client, mostrador, **params)).status_code == 422


async def test_clave_nueva_no_aparece_hasta_confirmar(client) -> None:
    """Un borrador creado con clave nueva no aparece en el listado por defecto."""
    duena = await login_duena(client)
    a = await _producto(client, duena)
    await crear_venta(client, duena, [(a, 1)], clave=clave_nueva())
    assert (await _listar(client, duena)).json()["items"] == []
