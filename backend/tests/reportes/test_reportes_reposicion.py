"""Reporte de reposicion por minimo y rotacion (C-14 task 7.1, RED-first, D9/D12).

GET /api/reportes/reposicion: productos activos bajo el minimo (mismo
criterio que /api/stock/alertas) o con cobertura corta segun las ventas
confirmadas de la ventana. Sin costos ni importes; lo ven duena y mostrador.
En RED fallan: el endpoint no existe (404).
"""

import pytest

from tests.reportes_helpers import (
    fijar_ahora,
    get_reporte,
    login_duena,
    login_mostrador,
    pago,
    post_anular,
    utc,
    venta_confirmada_en,
)

HOY = utc(2026, 10, 6, 15, 0)
ESTA_SEMANA = utc(2026, 10, 2, 15, 0)
HACE_45_DIAS = utc(2026, 8, 22, 15, 0)


@pytest.fixture(autouse=True)
def reloj_fijo(monkeypatch):
    fijar_ahora(monkeypatch, HOY)


async def _producto(client, duena, sku, stock, minimo, **extra) -> str:
    """Producto a precio 100 (costo 100, margen 0) con stock y minimo dados."""
    response = await client.post(
        "/api/productos",
        json={
            "sku": sku,
            "nombre": f"Producto {sku}",
            "costo": 100,
            "margen_pct": 0,
            "stock_actual": stock,
            "stock_minimo": minimo,
            **extra,
        },
        headers=duena,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _vender(client, duena, db, producto_id, cantidad, instante=ESTA_SEMANA):
    return await venta_confirmada_en(
        client, duena, db, [(producto_id, cantidad)], [pago(monto=100 * cantidad)], instante
    )


async def _reposicion(client, headers, **params) -> dict:
    response = await get_reporte(client, headers, "reposicion", **params)
    assert response.status_code == 200, response.text
    return response.json()


def _por_sku(cuerpo: dict) -> dict:
    return {i["sku"]: i for i in cuerpo["items"]}


# --- Condicion (a): bajo minimo ---


async def test_bajo_minimo_sin_ventas(client) -> None:
    duena = await login_duena(client)
    await _producto(client, duena, "RP-A", stock=2, minimo=3)
    cuerpo = await _reposicion(client, duena)
    assert (cuerpo["dias"], cuerpo["cobertura_max_dias"]) == (30, 7)
    item = _por_sku(cuerpo)["RP-A"]
    assert item["bajo_minimo"] is True
    assert (item["stock_actual"], item["stock_minimo"]) == (2, 3)
    assert item["unidades_vendidas"] == 0
    assert item["venta_diaria"] == 0
    assert item["cobertura_dias"] is None


async def test_stock_igual_al_minimo_cuenta_como_bajo_minimo(client) -> None:
    duena = await login_duena(client)
    await _producto(client, duena, "RP-IGUAL", stock=3, minimo=3)
    assert "RP-IGUAL" in _por_sku(await _reposicion(client, duena))


async def test_sobre_el_minimo_y_sin_ventas_no_aparece(client) -> None:
    duena = await login_duena(client)
    await _producto(client, duena, "RP-SOBRA", stock=10, minimo=2)
    assert await _reposicion(client, duena) == {"dias": 30, "cobertura_max_dias": 7, "items": []}


# --- Condicion (b): cobertura corta ---


async def test_rotacion_alta_sobre_el_minimo(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-ROT", stock=70, minimo=2)
    await _vender(client, duena, db_session_factory, a, 60)
    item = _por_sku(await _reposicion(client, duena))["RP-ROT"]
    assert item["stock_actual"] == 10
    assert item["bajo_minimo"] is False
    assert item["unidades_vendidas"] == 60
    assert item["venta_diaria"] == 2
    assert item["cobertura_dias"] == 5


async def test_rotacion_baja_sobre_el_minimo_no_aparece(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-LENTO", stock=13, minimo=2)
    await _vender(client, duena, db_session_factory, a, 3)  # cobertura 10*30/3 = 100 dias
    assert "RP-LENTO" not in _por_sku(await _reposicion(client, duena))


async def test_el_limite_de_cobertura_es_inclusivo(
    client, db_session_factory
) -> None:
    """Stock 20 a 30 u/30 d = 20 dias: entra con maximo 20, no con 19."""
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-LIM", stock=50, minimo=2)
    await _vender(client, duena, db_session_factory, a, 30)
    assert _por_sku(await _reposicion(client, duena, cobertura_max_dias=20))["RP-LIM"][
        "cobertura_dias"
    ] == 20
    assert "RP-LIM" not in _por_sku(await _reposicion(client, duena, cobertura_max_dias=19))


async def test_venta_diaria_a_centavos_mitad_hacia_arriba(client, db_session_factory) -> None:
    """7 u en 30 dias = 0.2333.. u/dia -> 0.23; 5 u = 0.1666.. -> 0.17."""
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-V7", stock=8, minimo=2)
    b = await _producto(client, duena, "RP-V5", stock=6, minimo=2)
    await _vender(client, duena, db_session_factory, a, 7)  # stock 1 -> bajo minimo
    await _vender(client, duena, db_session_factory, b, 5)  # stock 1 -> bajo minimo
    items = _por_sku(await _reposicion(client, duena))
    assert items["RP-V7"]["venta_diaria"] == 0.23
    assert items["RP-V5"]["venta_diaria"] == 0.17
    # La cobertura trunca: 1 u de stock a 7 u/30 d = 4.28 -> 4; a 5 u/30 d = 6 exacto.
    assert (items["RP-V7"]["cobertura_dias"], items["RP-V5"]["cobertura_dias"]) == (4, 6)


# --- La ventana y quien cuenta ---


async def test_ventas_fuera_de_la_ventana_o_anuladas_no_cuentan(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-VIEJO", stock=100, minimo=65)
    await _vender(client, duena, db_session_factory, a, 40, HACE_45_DIAS)
    anulable = await _vender(client, duena, db_session_factory, a, 20)
    assert (await post_anular(client, duena, anulable["id"])).status_code == 200
    # stock 60 <= 65: aparece por (a), pero sin rotacion en la ventana.
    item = _por_sku(await _reposicion(client, duena, dias=30))["RP-VIEJO"]
    assert item["unidades_vendidas"] == 0
    assert item["cobertura_dias"] is None


async def test_la_ventana_incluye_hoy_y_arranca_a_la_medianoche_local(
    client, db_session_factory
) -> None:
    """dias=30 con hoy 2026-10-06 abarca desde 2026-09-07 00:00 local (03:00Z)."""
    duena = await login_duena(client)
    dentro = await _producto(client, duena, "RP-DENTRO", stock=10, minimo=20)
    fuera = await _producto(client, duena, "RP-FUERA", stock=10, minimo=20)
    hoy = await _producto(client, duena, "RP-HOY", stock=10, minimo=20)
    await _vender(client, duena, db_session_factory, dentro, 2, utc(2026, 9, 7, 3, 0))
    await _vender(client, duena, db_session_factory, fuera, 2, utc(2026, 9, 7, 2, 59, 59))
    await _vender(client, duena, db_session_factory, hoy, 2, utc(2026, 10, 7, 2, 59))
    items = _por_sku(await _reposicion(client, duena))
    assert items["RP-DENTRO"]["unidades_vendidas"] == 2
    assert items["RP-FUERA"]["unidades_vendidas"] == 0
    assert items["RP-HOY"]["unidades_vendidas"] == 2


async def test_dias_cambia_la_ventana_y_el_resultado(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-DIAS", stock=40, minimo=2)
    await _vender(client, duena, db_session_factory, a, 30, HACE_45_DIAS)  # stock 10
    por_defecto = await _reposicion(client, duena, cobertura_max_dias=30)
    assert "RP-DIAS" not in _por_sku(por_defecto)  # 45 dias atras: fuera de 30
    ampliada = await _reposicion(client, duena, dias=60, cobertura_max_dias=30)
    item = _por_sku(ampliada)["RP-DIAS"]
    assert (ampliada["dias"], item["unidades_vendidas"], item["cobertura_dias"]) == (60, 30, 20)
    assert item["venta_diaria"] == 0.5


async def test_productos_dados_de_baja_no_aparecen(client) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-BAJA", stock=0, minimo=5)
    await _producto(client, duena, "RP-ACTIVO", stock=0, minimo=5)
    assert (await client.delete(f"/api/productos/{a}", headers=duena)).status_code == 204
    assert set(_por_sku(await _reposicion(client, duena))) == {"RP-ACTIVO"}


# --- Coherencia con las alertas de C-05 ---


async def test_coincide_con_las_alertas_de_bajo_minimo(client) -> None:
    duena = await login_duena(client)
    await _producto(client, duena, "RP-S1", stock=1, minimo=5)
    await _producto(client, duena, "RP-S2", stock=5, minimo=5)
    await _producto(client, duena, "RP-S3", stock=0, minimo=3)
    await _producto(client, duena, "RP-S4", stock=20, minimo=5)
    baja = await _producto(client, duena, "RP-S5", stock=0, minimo=3)
    assert (await client.delete(f"/api/productos/{baja}", headers=duena)).status_code == 204
    alertas = (await client.get("/api/stock/alertas", headers=duena)).json()
    items = _por_sku(await _reposicion(client, duena))
    en_alerta = {i["sku"] for i in alertas["items"]}
    assert en_alerta == {"RP-S1", "RP-S2", "RP-S3"}
    assert en_alerta == {sku for sku, i in items.items() if i["bajo_minimo"]}
    assert "RP-S5" not in items and "RP-S4" not in items


# --- Orden ---


async def test_orden_por_cobertura_con_null_al_final(client, db_session_factory) -> None:
    duena = await login_duena(client)
    agotado = await _producto(client, duena, "RP-O0", stock=10, minimo=0)
    cinco = await _producto(client, duena, "RP-O5", stock=70, minimo=2)
    await _producto(client, duena, "RP-ONULL", stock=1, minimo=3)  # bajo minimo sin ventas
    await _vender(client, duena, db_session_factory, agotado, 10)  # stock 0, cobertura 0
    await _vender(client, duena, db_session_factory, cinco, 60)  # stock 10, cobertura 5
    cuerpo = await _reposicion(client, duena)
    assert [i["sku"] for i in cuerpo["items"]] == ["RP-O0", "RP-O5", "RP-ONULL"]
    assert [i["cobertura_dias"] for i in cuerpo["items"]] == [0, 5, None]


async def test_empate_de_cobertura_desempata_por_holgura_y_luego_id(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    # Ambos con cobertura 5; difieren en stock - minimo (8 y 3).
    holgado = await _producto(client, duena, "RP-T1", stock=70, minimo=2)
    justo = await _producto(client, duena, "RP-T2", stock=70, minimo=7)
    await _vender(client, duena, db_session_factory, holgado, 60)
    await _vender(client, duena, db_session_factory, justo, 60)
    # Sin ventas y mismo stock - minimo: desempata producto_id.
    gemelos = [await _producto(client, duena, f"RP-G{i}", stock=1, minimo=3) for i in range(3)]
    cuerpo = await _reposicion(client, duena)
    skus = [i["sku"] for i in cuerpo["items"]]
    assert skus[:2] == ["RP-T2", "RP-T1"]
    ids_gemelos = [i["producto_id"] for i in cuerpo["items"] if i["sku"].startswith("RP-G")]
    assert ids_gemelos == sorted(gemelos)


# --- Contenido, acceso y validacion ---


async def test_la_respuesta_no_tiene_costos_precios_ni_importes(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "RP-SC", stock=70, minimo=2)
    await _vender(client, duena, db_session_factory, a, 60)
    item = (await _reposicion(client, duena))["items"][0]
    assert set(item) == {
        "producto_id",
        "sku",
        "nombre",
        "stock_actual",
        "stock_minimo",
        "bajo_minimo",
        "unidades_vendidas",
        "venta_diaria",
        "cobertura_dias",
        "distribuidora_default_id",
    }


async def test_mostrador_ve_los_mismos_items_que_la_duena(client, db_session_factory) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena, "RP-M1", stock=70, minimo=2)
    await _producto(client, duena, "RP-M2", stock=1, minimo=3)
    await _vender(client, duena, db_session_factory, a, 60)
    de_duena = await get_reporte(client, duena, "reposicion")
    de_mostrador = await get_reporte(client, mostrador, "reposicion")
    assert de_mostrador.status_code == 200
    assert de_mostrador.json() == de_duena.json()
    assert len(de_mostrador.json()["items"]) == 2


async def test_anonimo_401(client) -> None:
    assert (await client.get("/api/reportes/reposicion")).status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {"dias": 6},
        {"dias": 181},
        {"cobertura_max_dias": 0},
        {"cobertura_max_dias": 91},
        {"vendedor": "x"},
        {"dias": "treinta"},
    ],
)
async def test_parametros_invalidos_422(client, params) -> None:
    duena = await login_duena(client)
    assert (await get_reporte(client, duena, "reposicion", **params)).status_code == 422
