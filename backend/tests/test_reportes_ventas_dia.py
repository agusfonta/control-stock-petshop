"""Reporte de ventas del dia (C-14 task 5.2, RED-first, D4/D5/D7/D12).

GET /api/reportes/ventas-dia: solo ventas confirmadas, imputadas al dia local
del negocio por `confirmada_at` (America/Argentina/Buenos_Aires, UTC-3),
con anuladas como contador aparte y alcance segun el rol. En RED fallan: el
router de reportes no existe (404).
"""

import pytest

from tests.reportes_helpers import (
    contar,
    crear_producto,
    fijar_ahora,
    get_reporte,
    login_duena,
    login_mostrador,
    pago,
    post_anular,
    post_venta,
    utc,
    venta_confirmada_en,
)

METODOS = ["efectivo", "transferencia", "mp", "tarjeta"]
MEDIODIA_5 = utc(2026, 10, 5, 15, 0)  # 12:00 del 5/10 en Argentina


def _por_metodo(cuerpo: dict) -> dict:
    return {m["metodo"]: (m["monto"], m["cantidad_pagos"]) for m in cuerpo["por_metodo"]}


async def _a_y_b(client, duena, stock=50):
    """A (precio 1500) y B (precio 800)."""
    a = await crear_producto(client, duena, sku="RD-A", costo=1000, margen_pct=0.5, stock_actual=stock)
    b = await crear_producto(client, duena, sku="RD-B", costo=800, margen_pct=0, stock_actual=stock)
    return a, b


# --- Imputacion por dia local (D4/D5) ---


async def test_venta_a_las_0230z_cuenta_el_dia_anterior_y_a_las_0300z_el_nuevo(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)], [pago(monto=1500)], utc(2026, 10, 6, 2, 30)
    )
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 2)], [pago(monto=3000)], utc(2026, 10, 6, 3, 0)
    )
    dia_5 = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    dia_6 = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-06")).json()
    assert (dia_5["cantidad_ventas"], dia_5["total_vendido"]) == (1, 1500)
    assert (dia_6["cantidad_ventas"], dia_6["total_vendido"]) == (1, 3000)


async def test_ultimo_microsegundo_del_dia_local_y_el_primero_del_siguiente(
    client, db_session_factory
) -> None:
    """02:59:59.999999Z es del 5/10; 03:00:00Z es del 6/10 (borde inclusivo)."""
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)], [pago(monto=1500)],
        utc(2026, 10, 6, 2, 59, 59, 999999),
    )
    dia_5 = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    dia_6 = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-06")).json()
    assert (dia_5["cantidad_ventas"], dia_6["cantidad_ventas"]) == (1, 0)


async def test_sin_fecha_el_reporte_es_el_de_hoy_en_la_zona_del_negocio(
    client, db_session_factory, monkeypatch
) -> None:
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)], [pago(monto=1500)], utc(2026, 10, 6, 15, 0)
    )
    # 22:00 del 6/10 en Argentina: en UTC ya es el 7/10.
    fijar_ahora(monkeypatch, utc(2026, 10, 7, 1, 0))
    cuerpo = (await get_reporte(client, duena, "ventas-dia")).json()
    assert cuerpo["fecha"] == "2026-10-06"
    assert (cuerpo["cantidad_ventas"], cuerpo["total_vendido"]) == (1, 1500)


# --- Contenido del reporte (D7) ---


async def test_dia_con_efectivo_y_pago_mixto(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 2), (b, 1)], [pago("efectivo", 3800)], MEDIODIA_5
    )
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)],
        [pago("efectivo", 500), pago("mp", 1000)], MEDIODIA_5,
    )
    response = await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")
    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["fecha"] == "2026-10-05"
    assert cuerpo["alcance"] == "todas"
    assert cuerpo["cantidad_ventas"] == 2
    assert cuerpo["total_vendido"] == 5300
    assert cuerpo["ticket_promedio"] == 2650
    assert cuerpo["unidades_vendidas"] == 4
    assert [m["metodo"] for m in cuerpo["por_metodo"]] == METODOS
    assert _por_metodo(cuerpo) == {
        "efectivo": (4300, 2),
        "transferencia": (0, 0),
        "mp": (1000, 1),
        "tarjeta": (0, 0),
    }
    assert cuerpo["anuladas"] == {"cantidad": 0, "total": 0}
    # RN-VT-04: los pagos suman el total vendido.
    assert sum(m["monto"] for m in cuerpo["por_metodo"]) == cuerpo["total_vendido"]


async def test_ticket_promedio_se_redondea_a_centavos(client, db_session_factory) -> None:
    duena = await login_duena(client)
    uno = await crear_producto(client, duena, sku="RD-T1", costo=100, margen_pct=0, stock_actual=9)
    dos = await crear_producto(client, duena, sku="RD-T2", costo=100.01, margen_pct=0, stock_actual=9)
    for producto, monto in ((uno, 100), (uno, 100), (dos, 100.01)):
        await venta_confirmada_en(
            client, duena, db_session_factory, [(producto, 1)], [pago(monto=monto)], MEDIODIA_5
        )
    cuerpo = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert cuerpo["cantidad_ventas"] == 3
    assert cuerpo["total_vendido"] == 300.01
    assert cuerpo["ticket_promedio"] == 100


async def test_ticket_promedio_mitad_hacia_arriba(client, db_session_factory) -> None:
    """Dos ventas de total 100 y 100.01: 100.005 sube a 100.01."""
    duena = await login_duena(client)
    uno = await crear_producto(client, duena, sku="RD-H1", costo=100, margen_pct=0, stock_actual=9)
    dos = await crear_producto(client, duena, sku="RD-H2", costo=100.01, margen_pct=0, stock_actual=9)
    for producto, monto in ((uno, 100), (dos, 100.01)):
        await venta_confirmada_en(
            client, duena, db_session_factory, [(producto, 1)], [pago(monto=monto)], MEDIODIA_5
        )
    cuerpo = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert cuerpo["ticket_promedio"] == 100.01


async def test_dia_sin_ventas_responde_ceros_con_los_cuatro_metodos(client) -> None:
    duena = await login_duena(client)
    response = await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")
    assert response.status_code == 200
    cuerpo = response.json()
    assert (
        cuerpo["cantidad_ventas"],
        cuerpo["total_vendido"],
        cuerpo["ticket_promedio"],
        cuerpo["unidades_vendidas"],
    ) == (0, 0, 0, 0)
    assert _por_metodo(cuerpo) == {m: (0, 0) for m in METODOS}
    assert [m["metodo"] for m in cuerpo["por_metodo"]] == METODOS
    assert cuerpo["anuladas"] == {"cantidad": 0, "total": 0}


# --- Borradores y anuladas (D4) ---


async def test_borrador_no_suma(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 2), (b, 1)], [pago(monto=3800)], MEDIODIA_5
    )
    borrador = await post_venta(client, duena, [(b, 1)])
    assert borrador.status_code == 201
    cuerpo = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert (cuerpo["cantidad_ventas"], cuerpo["total_vendido"]) == (1, 3800)


async def test_anulada_se_informa_aparte_y_no_suma(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 2), (b, 1)], [pago(monto=3800)], MEDIODIA_5
    )
    anulable = await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)], [pago("mp", 1500)], MEDIODIA_5
    )
    assert (await post_anular(client, duena, anulable["id"])).status_code == 200
    cuerpo = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert cuerpo["cantidad_ventas"] == 1
    assert cuerpo["total_vendido"] == 3800
    assert cuerpo["unidades_vendidas"] == 3
    assert _por_metodo(cuerpo)["mp"] == (0, 0)
    assert cuerpo["anuladas"] == {"cantidad": 1, "total": 1500}


async def test_anulada_se_cuenta_en_el_dia_de_su_confirmacion_no_en_el_de_la_anulacion(
    client, db_session_factory
) -> None:
    """Anulada hoy una venta confirmada el 5/10: aparece en el 5/10, no en hoy."""
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    venta = await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)], [pago(monto=1500)], MEDIODIA_5
    )
    assert (await post_anular(client, duena, venta["id"])).status_code == 200
    dia_5 = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    otro = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-06")).json()
    assert dia_5["anuladas"] == {"cantidad": 1, "total": 1500}
    assert otro["anuladas"] == {"cantidad": 0, "total": 0}


# --- Alcance por rol (D12) ---


async def test_mostrador_ve_solo_sus_ventas_y_la_duena_todas(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, b = await _a_y_b(client, duena)
    await venta_confirmada_en(
        client, mostrador, db_session_factory, [(a, 2), (b, 1)], [pago(monto=3800)], MEDIODIA_5
    )
    ajena = await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)], [pago(monto=1500)], MEDIODIA_5
    )
    propias = (await get_reporte(client, mostrador, "ventas-dia", fecha="2026-10-05")).json()
    todas = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert (propias["alcance"], propias["cantidad_ventas"], propias["total_vendido"]) == (
        "propias",
        1,
        3800,
    )
    assert propias["unidades_vendidas"] == 3
    assert (todas["alcance"], todas["cantidad_ventas"], todas["total_vendido"]) == ("todas", 2, 5300)
    # La anulada ajena tampoco se filtra al mostrador.
    assert (await post_anular(client, duena, ajena["id"])).status_code == 200
    propias = (await get_reporte(client, mostrador, "ventas-dia", fecha="2026-10-05")).json()
    assert propias["anuladas"] == {"cantidad": 0, "total": 0}


# --- Autenticacion y validacion ---


async def test_anonimo_401(client) -> None:
    response = await client.get("/api/reportes/ventas-dia")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {"fecha": "06/10/2026"},
        {"fecha": "2026-10-06T10:00:00"},
        {"fecha": "2026-10-06T00:00:00"},
        {"fecha": ""},
        {"vendedor": "x"},
        {"desde": "2026-10-01"},
    ],
)
async def test_parametros_invalidos_422(client, params) -> None:
    duena = await login_duena(client)
    response = await get_reporte(client, duena, "ventas-dia", **params)
    assert response.status_code == 422


async def test_no_crea_ni_modifica_nada(client, db_session_factory) -> None:
    """Solo lectura: consultar un reporte no escribe ventas."""
    from app.models import Venta

    duena = await login_duena(client)
    await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")
    assert contar(db_session_factory, Venta) == 0
