"""Reporte de margenes con costo historico (C-14 task 8.1, RED-first, D1/D10/D12).

GET /api/reportes/margenes: por producto y total, sobre las lineas de ventas
confirmadas con costo congelado (D1). El margen NUNCA usa el costo actual del
producto; las lineas sin costo se informan aparte. Solo duena. En RED fallan:
el endpoint no existe (404).
"""

import pytest

from tests.reportes_helpers import (
    crear_producto,
    get_reporte,
    insertar_venta_confirmada,
    login_duena,
    login_mostrador,
    pago,
    post_anular,
    post_venta,
    usuario_id,
    utc,
    venta_confirmada_en,
)

DIA = utc(2026, 10, 5, 15, 0)  # 12:00 del 5/10 en Argentina
PERIODO = {"desde": "2026-10-01", "hasta": "2026-10-06"}


async def _margenes(client, headers, **params) -> dict:
    response = await get_reporte(client, headers, "margenes", **{**PERIODO, **params})
    assert response.status_code == 200, response.text
    return response.json()


async def _producto(client, duena, sku, costo, margen_pct=0.5, stock=100) -> str:
    return await crear_producto(
        client, duena, sku=sku, costo=costo, margen_pct=margen_pct, stock_actual=stock
    )


async def _vender(client, duena, db, producto_id, cantidad, precio, instante=DIA):
    return await venta_confirmada_en(
        client, duena, db, [(producto_id, cantidad)], [pago(monto=round(precio * cantidad, 2))], instante
    )


def _por_sku(cuerpo: dict) -> dict:
    return {i["sku"]: i for i in cuerpo["items"]}


# --- Margen por producto y total ---


async def test_margen_por_producto_y_total(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-A", costo=1000)
    await _vender(client, duena, db_session_factory, a, 2, 1500)
    cuerpo = await _margenes(client, duena)
    assert (cuerpo["desde"], cuerpo["hasta"]) == ("2026-10-01", "2026-10-06")
    (item,) = cuerpo["items"]
    assert (item["producto_id"], item["sku"]) == (a, "MG-A")
    assert (item["unidades"], item["ingresos"], item["costo"]) == (2, 3000, 2000)
    assert (item["margen_bruto"], item["margen_pct"]) == (1000, 0.5)
    assert cuerpo["totales"] == {
        "ingresos": 3000,
        "costo": 2000,
        "margen_bruto": 1000,
        "margen_pct": 0.5,
        "lineas_sin_costo": 0,
        "ingresos_sin_costo": 0,
    }
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"], cuerpo["total_pages"]) == (
        1,
        1,
        20,
        1,
    )


async def test_cambio_de_costo_posterior_no_altera_margenes_pasados(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-B", costo=1000)
    await _vender(client, duena, db_session_factory, a, 2, 1500)
    # Una recepcion/edicion sube el costo a 1200: el precio pasa a 1800.
    subida = await client.put(f"/api/productos/{a}", json={"costo": 1200}, headers=duena)
    assert subida.status_code == 200
    await _vender(client, duena, db_session_factory, a, 1, 1800)
    (item,) = (await _margenes(client, duena))["items"]
    assert (item["unidades"], item["ingresos"], item["costo"]) == (3, 4800, 3200)
    assert (item["margen_bruto"], item["margen_pct"]) == (1600, 0.5)


async def test_margen_agrega_productos_y_ordena_por_margen_bruto(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-1", costo=1000)  # precio 1500
    b = await _producto(client, duena, "MG-2", costo=800, margen_pct=0)  # precio 800
    c = await _producto(client, duena, "MG-3", costo=100, margen_pct=1)  # precio 200
    await _vender(client, duena, db_session_factory, b, 1, 800)
    await _vender(client, duena, db_session_factory, c, 3, 200)
    await _vender(client, duena, db_session_factory, a, 2, 1500)
    cuerpo = await _margenes(client, duena)
    assert [(i["sku"], i["margen_bruto"]) for i in cuerpo["items"]] == [
        ("MG-1", 1000),
        ("MG-3", 300),
        ("MG-2", 0),
    ]
    assert cuerpo["items"][2]["margen_pct"] == 0
    totales = cuerpo["totales"]
    assert (totales["ingresos"], totales["costo"], totales["margen_bruto"]) == (4400, 3100, 1300)
    assert totales["margen_pct"] == 0.4194  # 1300 / 3100 = 0.41935..


async def test_margen_con_centavos_no_arrastra_error_de_float(
    client, db_session_factory
) -> None:
    """costo 10.03, precio 15.05 (15.045 sube): 3 u = 45.15 vs 30.09."""
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-C", costo=10.03)
    await _vender(client, duena, db_session_factory, a, 3, 15.05)
    (item,) = (await _margenes(client, duena))["items"]
    assert (item["ingresos"], item["costo"], item["margen_bruto"]) == (45.15, 30.09, 15.06)
    assert item["margen_pct"] == 0.5005


async def test_venta_bajo_el_costo_da_margen_negativo(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-N", costo=1000)
    me = await usuario_id(client, duena)
    insertar_venta_confirmada(db_session_factory, me, [(a, 2, 800, 1000)], DIA)
    (item,) = (await _margenes(client, duena))["items"]
    assert (item["ingresos"], item["costo"], item["margen_bruto"]) == (1600, 2000, -400)
    assert item["margen_pct"] == -0.2


# --- Lineas sin costo congelado (D1) ---


async def test_lineas_sin_costo_se_informan_aparte(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-D", costo=1000)
    b = await _producto(client, duena, "MG-E", costo=500)
    me = await usuario_id(client, duena)
    await _vender(client, duena, db_session_factory, a, 2, 1500)
    # B solo tiene una linea sin costo (como las previas a la migracion 0008).
    insertar_venta_confirmada(db_session_factory, me, [(b, 1, 900, None)], DIA)
    # A tiene ademas una linea sin costo: no debe sumar a sus ingresos.
    insertar_venta_confirmada(db_session_factory, me, [(a, 1, 1500, None)], DIA)
    cuerpo = await _margenes(client, duena)
    assert list(_por_sku(cuerpo)) == ["MG-D"]
    a_item = _por_sku(cuerpo)["MG-D"]
    assert (a_item["unidades"], a_item["ingresos"], a_item["costo"]) == (2, 3000, 2000)
    assert cuerpo["totales"] == {
        "ingresos": 3000,
        "costo": 2000,
        "margen_bruto": 1000,
        "margen_pct": 0.5,
        "lineas_sin_costo": 2,
        "ingresos_sin_costo": 2400,
    }
    assert cuerpo["total"] == 1


async def test_solo_lineas_sin_costo_da_lista_vacia_y_margen_null(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    b = await _producto(client, duena, "MG-F", costo=500)
    me = await usuario_id(client, duena)
    insertar_venta_confirmada(db_session_factory, me, [(b, 1, 900, None)], DIA)
    cuerpo = await _margenes(client, duena)
    assert cuerpo["items"] == []
    assert cuerpo["totales"]["margen_pct"] is None
    assert (cuerpo["totales"]["lineas_sin_costo"], cuerpo["totales"]["ingresos_sin_costo"]) == (
        1,
        900,
    )


# --- Periodo y quien cuenta ---


async def test_periodo_sin_ventas_da_ceros_y_margen_null(client) -> None:
    duena = await login_duena(client)
    cuerpo = await _margenes(client, duena)
    assert cuerpo["items"] == []
    assert (cuerpo["total"], cuerpo["total_pages"]) == (0, 0)
    assert cuerpo["totales"] == {
        "ingresos": 0,
        "costo": 0,
        "margen_bruto": 0,
        "margen_pct": None,
        "lineas_sin_costo": 0,
        "ingresos_sin_costo": 0,
    }


async def test_solo_cuentan_las_ventas_del_periodo(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-P", costo=1000)
    await _vender(client, duena, db_session_factory, a, 1, 1500, utc(2026, 9, 30, 15, 0))
    await _vender(client, duena, db_session_factory, a, 2, 1500, utc(2026, 10, 1, 3, 0))
    await _vender(client, duena, db_session_factory, a, 4, 1500, utc(2026, 10, 7, 3, 0))
    (item,) = (await _margenes(client, duena))["items"]
    assert item["unidades"] == 2  # ni 30/9 ni 7/10 (03:00Z ya es el dia siguiente al periodo)


async def test_anuladas_y_borradores_no_cuentan(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MG-G", costo=1000)
    b = await _producto(client, duena, "MG-H", costo=800, margen_pct=0)
    await _vender(client, duena, db_session_factory, a, 2, 1500)
    anulable = await _vender(client, duena, db_session_factory, b, 3, 800)
    assert (await post_anular(client, duena, anulable["id"])).status_code == 200
    assert (await post_venta(client, duena, [(b, 4)])).status_code == 201  # borrador
    cuerpo = await _margenes(client, duena)
    assert list(_por_sku(cuerpo)) == ["MG-G"]
    assert cuerpo["totales"]["ingresos"] == 3000


# --- Paginacion ---


async def test_paginacion_con_totales_sobre_todo_el_periodo(client, db_session_factory) -> None:
    duena = await login_duena(client)
    for n, sku in enumerate(["MG-X1", "MG-X2", "MG-X3"], start=1):
        producto_id = await _producto(client, duena, sku, costo=100)  # precio 150
        await _vender(client, duena, db_session_factory, producto_id, n, 150)
    primera = await _margenes(client, duena, page_size=1)
    segunda = await _margenes(client, duena, page_size=1, page=2)
    fuera = await _margenes(client, duena, page_size=1, page=4)
    assert (primera["total"], primera["total_pages"], primera["page_size"]) == (3, 3, 1)
    assert [i["sku"] for i in primera["items"]] == ["MG-X3"]  # mayor margen bruto
    assert [i["sku"] for i in segunda["items"]] == ["MG-X2"]
    assert fuera["items"] == []
    # Los totales cubren las 3 filas aunque la pagina tenga una.
    for cuerpo in (primera, segunda, fuera):
        assert cuerpo["totales"]["ingresos"] == 900
        assert cuerpo["totales"]["margen_bruto"] == 300


async def test_empate_de_margen_desempata_por_producto_id(client, db_session_factory) -> None:
    duena = await login_duena(client)
    ids = []
    for sku in ("MG-T1", "MG-T2", "MG-T3"):
        producto_id = await _producto(client, duena, sku, costo=100)
        await _vender(client, duena, db_session_factory, producto_id, 2, 150)
        ids.append(producto_id)
    cuerpo = await _margenes(client, duena)
    assert [i["producto_id"] for i in cuerpo["items"]] == sorted(ids)


# --- Acceso y validacion ---


async def test_mostrador_403(client) -> None:
    mostrador = await login_mostrador(client)
    assert (await get_reporte(client, mostrador, "margenes")).status_code == 403


async def test_anonimo_401(client) -> None:
    assert (await client.get("/api/reportes/margenes")).status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "2026-10-06", "hasta": "2026-10-01"},
        {"desde": "2025-10-05", "hasta": "2026-10-06"},
        {"page_size": 101},
        {"page_size": 0},
        {"page": 0},
        {"vendedor": "x"},
        {"hasta": "2026-10-06T10:00:00"},
    ],
)
async def test_parametros_invalidos_422(client, params) -> None:
    duena = await login_duena(client)
    response = await client.get("/api/reportes/margenes", params=params, headers=duena)
    assert response.status_code == 422
