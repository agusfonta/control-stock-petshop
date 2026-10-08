"""Reporte de productos mas vendidos (C-14 task 6.1, RED-first, D6/D8/D12).

GET /api/reportes/mas-vendidos: ranking top-N del periodo sobre ventas
confirmadas, por unidades (default) o monto, con desempate determinista.
Solo duena. En RED fallan: el endpoint no existe (404).
"""

import pytest

from tests.reportes_helpers import (
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

DIA = utc(2026, 10, 5, 15, 0)  # 12:00 del 5/10 en Argentina


async def _vender(client, duena, db, producto_id, cantidad, precio, instante=DIA):
    """Una venta confirmada de `cantidad` unidades a `precio` (pago exacto)."""
    return await venta_confirmada_en(
        client, duena, db, [(producto_id, cantidad)], [pago(monto=precio * cantidad)], instante
    )


async def _producto(client, duena, sku, precio, stock=100):
    """Producto con precio_venta = `precio` (margen 0)."""
    return await crear_producto(client, duena, sku=sku, costo=precio, margen_pct=0, stock_actual=stock)


def _skus(cuerpo: dict) -> list[str]:
    return [i["sku"] for i in cuerpo["items"]]


async def _a_5_y_b_8(client, duena, db):
    """A: 5 u por 7500 (a 1500); B: 8 u por 2400 (a 300)."""
    a = await _producto(client, duena, "MV-A", 1500)
    b = await _producto(client, duena, "MV-B", 300)
    await _vender(client, duena, db, a, 3, 1500)
    await _vender(client, duena, db, a, 2, 1500)
    await _vender(client, duena, db, b, 8, 300)
    return a, b


# --- Orden ---


async def test_ranking_por_unidades_por_defecto(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b = await _a_5_y_b_8(client, duena, db_session_factory)
    response = await get_reporte(
        client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06"
    )
    assert response.status_code == 200
    cuerpo = response.json()
    assert (cuerpo["desde"], cuerpo["hasta"], cuerpo["orden"]) == (
        "2026-10-01",
        "2026-10-06",
        "cantidad",
    )
    assert [(i["producto_id"], i["unidades"], i["monto"]) for i in cuerpo["items"]] == [
        (b, 8, 2400),
        (a, 5, 7500),
    ]
    assert cuerpo["items"][0].keys() == {
        "producto_id",
        "sku",
        "nombre",
        "activo",
        "unidades",
        "monto",
    }
    assert cuerpo["items"][0]["activo"] is True


async def test_ranking_por_monto(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b = await _a_5_y_b_8(client, duena, db_session_factory)
    cuerpo = (
        await get_reporte(
            client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06", orden="monto"
        )
    ).json()
    assert cuerpo["orden"] == "monto"
    assert [i["producto_id"] for i in cuerpo["items"]] == [a, b]


async def test_empate_de_unidades_desempata_por_monto(client, db_session_factory) -> None:
    duena = await login_duena(client)
    barato = await _producto(client, duena, "MV-BARATO", 400)
    caro = await _producto(client, duena, "MV-CARO", 1500)
    # El barato se vende primero: el desempate no puede depender del orden de carga.
    await _vender(client, duena, db_session_factory, barato, 5, 400)
    await _vender(client, duena, db_session_factory, caro, 5, 1500)
    cuerpo = (
        await get_reporte(client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06")
    ).json()
    assert _skus(cuerpo) == ["MV-CARO", "MV-BARATO"]


async def test_empate_de_monto_con_orden_monto_desempata_por_unidades(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    pocas = await _producto(client, duena, "MV-POCAS", 1000)
    muchas = await _producto(client, duena, "MV-MUCHAS", 500)
    await _vender(client, duena, db_session_factory, pocas, 2, 1000)
    await _vender(client, duena, db_session_factory, muchas, 4, 500)
    cuerpo = (
        await get_reporte(
            client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06", orden="monto"
        )
    ).json()
    assert _skus(cuerpo) == ["MV-MUCHAS", "MV-POCAS"]


async def test_empate_total_desempata_por_producto_id(client, db_session_factory) -> None:
    duena = await login_duena(client)
    gemelos = [await _producto(client, duena, f"MV-G{i}", 100) for i in range(3)]
    for producto_id in gemelos:
        await _vender(client, duena, db_session_factory, producto_id, 2, 100)
    cuerpo = (
        await get_reporte(client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06")
    ).json()
    assert [i["producto_id"] for i in cuerpo["items"]] == sorted(gemelos)


# --- Limite ---


async def test_limite_devuelve_los_primeros_del_ranking(client, db_session_factory) -> None:
    duena = await login_duena(client)
    for n in range(1, 13):  # 12 productos: el n vende n unidades
        producto_id = await _producto(client, duena, f"MV-L{n:02d}", 100)
        await _vender(client, duena, db_session_factory, producto_id, n, 100)
    cuerpo = (
        await get_reporte(
            client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06", limite=3
        )
    ).json()
    assert _skus(cuerpo) == ["MV-L12", "MV-L11", "MV-L10"]
    por_defecto = (
        await get_reporte(client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06")
    ).json()
    assert len(por_defecto["items"]) == 10


# --- Periodo ---


async def test_periodo_por_defecto_son_los_ultimos_30_dias(
    client, db_session_factory, monkeypatch
) -> None:
    duena = await login_duena(client)
    fijar_ahora(monkeypatch, utc(2026, 10, 6, 15, 0))
    viejo = await _producto(client, duena, "MV-VIEJO", 100)
    borde = await _producto(client, duena, "MV-BORDE", 100)
    justo_antes = await _producto(client, duena, "MV-ANTES", 100)
    ultimo = await _producto(client, duena, "MV-HOY", 100)
    await _vender(client, duena, db_session_factory, viejo, 1, 100, utc(2026, 9, 6, 15, 0))
    # 2026-09-07 00:00 local = 03:00Z: primer instante del periodo.
    await _vender(client, duena, db_session_factory, borde, 1, 100, utc(2026, 9, 7, 3, 0))
    await _vender(
        client, duena, db_session_factory, justo_antes, 1, 100, utc(2026, 9, 7, 2, 59, 59)
    )
    await _vender(client, duena, db_session_factory, ultimo, 1, 100, utc(2026, 10, 7, 2, 59))
    cuerpo = (await get_reporte(client, duena, "mas-vendidos")).json()
    assert (cuerpo["desde"], cuerpo["hasta"]) == ("2026-09-07", "2026-10-06")
    assert set(_skus(cuerpo)) == {"MV-BORDE", "MV-HOY"}


async def test_un_solo_borde_completa_el_otro(client, monkeypatch) -> None:
    duena = await login_duena(client)
    fijar_ahora(monkeypatch, utc(2026, 10, 6, 15, 0))
    solo_desde = (await get_reporte(client, duena, "mas-vendidos", desde="2026-10-01")).json()
    assert (solo_desde["desde"], solo_desde["hasta"]) == ("2026-10-01", "2026-10-06")
    solo_hasta = (await get_reporte(client, duena, "mas-vendidos", hasta="2026-09-30")).json()
    assert (solo_hasta["desde"], solo_hasta["hasta"]) == ("2026-09-01", "2026-09-30")


async def test_un_dia_futuro_da_ranking_vacio(client, monkeypatch) -> None:
    duena = await login_duena(client)
    fijar_ahora(monkeypatch, utc(2026, 10, 6, 15, 0))
    response = await get_reporte(
        client, duena, "mas-vendidos", desde="2026-11-01", hasta="2026-11-30"
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


# --- Quien cuenta ---


async def test_producto_dado_de_baja_aparece_con_activo_false(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, b = await _a_5_y_b_8(client, duena, db_session_factory)
    assert (await client.delete(f"/api/productos/{b}", headers=duena)).status_code == 204
    cuerpo = (
        await get_reporte(client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06")
    ).json()
    por_id = {i["producto_id"]: i for i in cuerpo["items"]}
    assert por_id[b]["activo"] is False and por_id[b]["unidades"] == 8
    assert por_id[a]["activo"] is True


async def test_borradores_y_anuladas_no_cuentan(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "MV-X", 1500)
    b = await _producto(client, duena, "MV-Y", 800)
    await _vender(client, duena, db_session_factory, a, 2, 1500)
    anulada = await _vender(client, duena, db_session_factory, b, 3, 800)
    assert (await post_anular(client, duena, anulada["id"])).status_code == 200
    assert (await post_venta(client, duena, [(b, 4)])).status_code == 201  # borrador
    cuerpo = (
        await get_reporte(client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06")
    ).json()
    assert [(i["sku"], i["unidades"], i["monto"]) for i in cuerpo["items"]] == [
        ("MV-X", 2, 3000)
    ]


async def test_monto_con_centavos_no_pierde_precision(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await crear_producto(client, duena, sku="MV-C", costo=100.01, margen_pct=0, stock_actual=9)
    for _ in range(3):
        await venta_confirmada_en(
            client, duena, db_session_factory, [(a, 1)], [pago(monto=100.01)], DIA
        )
    cuerpo = (
        await get_reporte(client, duena, "mas-vendidos", desde="2026-10-01", hasta="2026-10-06")
    ).json()
    assert cuerpo["items"][0]["monto"] == 300.03


# --- Acceso y validacion ---


async def test_mostrador_403(client) -> None:
    mostrador = await login_mostrador(client)
    response = await get_reporte(client, mostrador, "mas-vendidos")
    assert response.status_code == 403


async def test_anonimo_401(client) -> None:
    assert (await client.get("/api/reportes/mas-vendidos")).status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "2026-10-06", "hasta": "2026-10-01"},
        {"desde": "2025-10-05", "hasta": "2026-10-06"},
        {"vendedor": "x"},
        {"orden": "ganancia"},
        {"limite": 0},
        {"limite": 51},
        {"desde": "06/10/2026"},
    ],
)
async def test_parametros_invalidos_422(client, params) -> None:
    duena = await login_duena(client)
    response = await get_reporte(client, duena, "mas-vendidos", **params)
    assert response.status_code == 422
