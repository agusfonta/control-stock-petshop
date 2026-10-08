"""Reportes siempre actualizados (C-14 task 9.1): sin cache ni recalculo diferido.

Una venta confirmada o anulada se ve en la consulta siguiente. Estos tests
pasan sin codigo nuevo (los agregados SQL corren al vuelo, D2): si algun dia
fallan, se corrige el servicio, nunca se agrega cache.
"""

from tests.reportes_helpers import (
    crear_producto,
    fijar_ahora,
    fijar_confirmada_at,
    get_reporte,
    login_duena,
    pago,
    post_anular,
    utc,
    venta_confirmada,
)

DIA = utc(2026, 10, 5, 15, 0)  # 12:00 del 5/10 en Argentina


async def _producto(client, duena, sku="FR-A", costo=1000, margen_pct=0.5):
    return await crear_producto(
        client, duena, sku=sku, costo=costo, margen_pct=margen_pct, stock_actual=50
    )


async def test_venta_confirmada_se_ve_en_la_consulta_siguiente(
    client, db_session_factory, monkeypatch
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    fijar_ahora(monkeypatch, utc(2026, 10, 5, 16, 0))
    antes = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert (antes["cantidad_ventas"], antes["total_vendido"]) == (0, 0)

    venta = await venta_confirmada(client, duena, [(a, 1)], [pago(monto=1500)])
    fijar_confirmada_at(db_session_factory, venta["id"], DIA)

    despues = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert despues["cantidad_ventas"] == antes["cantidad_ventas"] + 1
    assert despues["total_vendido"] == antes["total_vendido"] + 1500


async def test_cada_confirmacion_sucesiva_se_refleja_sin_esperar(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    totales = []
    for _ in range(3):
        venta = await venta_confirmada(client, duena, [(a, 1)], [pago(monto=1500)])
        fijar_confirmada_at(db_session_factory, venta["id"], DIA)
        cuerpo = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
        totales.append((cuerpo["cantidad_ventas"], cuerpo["total_vendido"]))
    assert totales == [(1, 1500), (2, 3000), (3, 4500)]


async def test_anulacion_se_ve_de_inmediato_en_margenes_ranking_y_reposicion(
    client, db_session_factory, monkeypatch
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    fijar_ahora(monkeypatch, utc(2026, 10, 6, 15, 0))
    periodo = {"desde": "2026-10-01", "hasta": "2026-10-06"}
    conservada = await venta_confirmada(client, duena, [(a, 2)], [pago(monto=3000)])
    anulable = await venta_confirmada(client, duena, [(a, 1)], [pago(monto=1500)])
    for venta in (conservada, anulable):
        fijar_confirmada_at(db_session_factory, venta["id"], DIA)

    margenes = (await get_reporte(client, duena, "margenes", **periodo)).json()
    ranking = (await get_reporte(client, duena, "mas-vendidos", **periodo)).json()
    assert margenes["items"][0]["unidades"] == 3
    assert margenes["totales"]["ingresos"] == 4500
    assert ranking["items"][0]["unidades"] == 3

    assert (await post_anular(client, duena, anulable["id"])).status_code == 200

    margenes = (await get_reporte(client, duena, "margenes", **periodo)).json()
    ranking = (await get_reporte(client, duena, "mas-vendidos", **periodo)).json()
    assert margenes["items"][0]["unidades"] == 2
    assert margenes["totales"]["ingresos"] == 3000
    assert margenes["totales"]["costo"] == 2000
    assert ranking["items"][0]["unidades"] == 2
    dia = (await get_reporte(client, duena, "ventas-dia", fecha="2026-10-05")).json()
    assert (dia["cantidad_ventas"], dia["anuladas"]["cantidad"]) == (1, 1)


async def test_reposicion_refleja_la_rotacion_apenas_se_confirma(
    client, db_session_factory, monkeypatch
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena)
    fijar_ahora(monkeypatch, utc(2026, 10, 6, 15, 0))
    assert (await get_reporte(client, duena, "reposicion")).json()["items"] == []
    venta = await venta_confirmada(client, duena, [(a, 45)], [pago(monto=67500)])
    fijar_confirmada_at(db_session_factory, venta["id"], DIA)
    (item,) = (await get_reporte(client, duena, "reposicion")).json()["items"]
    assert (item["stock_actual"], item["unidades_vendidas"], item["cobertura_dias"]) == (5, 45, 3)
