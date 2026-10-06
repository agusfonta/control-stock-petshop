"""Confirmar venta en una transaccion (C-10 task 6.1, RED-first).

POST /api/ventas/{id}/confirmar descuenta stock de TODAS las lineas con un
movimiento `venta` por linea (ref_id a la venta), valida pagos contra el
total (RN-VT-04), registra los pagos y el evento `venta.confirmada` y marca
la venta confirmada: todo o nada (RN-VT-01/02). En RED fallan: el endpoint
confirmar no existe (404/405).
"""

import pytest

from tests.ventas_helpers import (
    VENTAS_URL,
    clave_nueva,
    confirmar_venta,
    contar,
    crear_producto,
    crear_venta,
    get_producto,
    get_venta,
    login_duena,
    login_mostrador,
    movimientos_de,
    pago,
    post_confirmar,
    usuario_id,
)


async def _a_y_b(client, duena):
    """A (precio 1500, stock 5) y B (precio 800, stock 1)."""
    a = await crear_producto(client, duena, sku="CF-A", costo=1000, margen_pct=0.5, stock_actual=5)
    b = await crear_producto(client, duena, sku="CF-B", costo=800, margen_pct=0, stock_actual=1)
    return a, b


async def _borrador_ab(client, duena, headers):
    """Borrador de 2xA + 1xB (total 3800) creado con `headers`."""
    a, b = await _a_y_b(client, duena)
    venta = await crear_venta(client, headers, [(a, 2), (b, 1)])
    assert venta["total"] == 3800
    return a, b, venta


def _pagos_de(db_session_factory, venta_id: str) -> list:
    from app.models import PagoVenta

    with db_session_factory() as session:
        return session.query(PagoVenta).filter_by(venta_id=venta_id).all()


def _eventos_de(db_session_factory, venta_id: str) -> list:
    from app.models import EventoOutbox

    with db_session_factory() as session:
        return (
            session.query(EventoOutbox).filter_by(agregado_id=venta_id).all()
        )


async def _nada_cambio(client, duena, db_session_factory, a, b, venta_id) -> None:
    """Stock, movimientos, pagos y evento intactos; la venta sigue borrador."""
    assert (await get_producto(client, duena, a))["stock_actual"] == 5
    assert (await get_producto(client, duena, b))["stock_actual"] == 1
    assert movimientos_de(db_session_factory, a) == []
    assert movimientos_de(db_session_factory, b) == []
    assert _pagos_de(db_session_factory, venta_id) == []
    assert _eventos_de(db_session_factory, venta_id) == []
    venta = await get_venta(client, duena, venta_id)
    assert venta["estado"] == "borrador"
    assert venta["confirmada_at"] is None
    assert venta["pagos"] == []


# --- Confirmacion exitosa ---


async def test_confirmar_descuenta_stock_y_crea_un_movimiento_venta_por_linea(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, b, venta = await _borrador_ab(client, duena, mostrador)
    response = await post_confirmar(client, mostrador, venta["id"], [pago("efectivo", 3800)])
    assert response.status_code == 200
    body = response.json()
    assert body["estado"] == "confirmada"
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    assert (await get_producto(client, duena, b))["stock_actual"] == 0

    (mov_a,) = movimientos_de(db_session_factory, a)
    assert (mov_a.tipo, mov_a.cantidad) == ("venta", -2)
    assert (mov_a.stock_previo, mov_a.stock_nuevo) == (5, 3)
    assert mov_a.ref_id == venta["id"]
    assert mov_a.usuario_id == await usuario_id(client, mostrador)
    (mov_b,) = movimientos_de(db_session_factory, b)
    assert (mov_b.tipo, mov_b.cantidad) == ("venta", -1)
    assert (mov_b.stock_previo, mov_b.stock_nuevo) == (1, 0)
    assert mov_b.ref_id == venta["id"]


async def test_confirmar_registra_pago_auditoria_y_evento_pendiente(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    _, _, venta = await _borrador_ab(client, duena, mostrador)
    body = await confirmar_venta(client, mostrador, venta["id"], [pago("efectivo", 3800)])
    mostrador_id = await usuario_id(client, mostrador)
    assert body["confirmada_at"] is not None
    assert body["confirmada_por_id"] == mostrador_id
    assert body["usuario_id"] == mostrador_id
    assert [(p["metodo"], p["monto"], p["ref_mp"]) for p in body["pagos"]] == [
        ("efectivo", 3800, None)
    ]
    (pago_db,) = _pagos_de(db_session_factory, venta["id"])
    assert (pago_db.metodo, float(pago_db.monto)) == ("efectivo", 3800.0)
    (evento,) = _eventos_de(db_session_factory, venta["id"])
    assert evento.tipo == "venta.confirmada"
    assert evento.procesado_at is None
    # La venta queda legible con el mismo estado.
    assert (await get_venta(client, duena, venta["id"]))["estado"] == "confirmada"


async def test_pago_dividido_entre_metodos_200(client, db_session_factory) -> None:
    duena = await login_duena(client)
    _, _, venta = await _borrador_ab(client, duena, duena)
    body = await confirmar_venta(
        client,
        duena,
        venta["id"],
        [pago("efectivo", 1800), pago("mp", 2000, ref_mp="MP-123")],
    )
    assert sorted((p["metodo"], p["monto"], p["ref_mp"]) for p in body["pagos"]) == [
        ("efectivo", 1800, None),
        ("mp", 2000, "MP-123"),
    ]
    assert len(_pagos_de(db_session_factory, venta["id"])) == 2


async def test_pago_mp_sin_ref_mp_es_valido(client) -> None:
    duena = await login_duena(client)
    _, _, venta = await _borrador_ab(client, duena, duena)
    body = await confirmar_venta(client, duena, venta["id"], [pago("mp", 3800)])
    assert body["pagos"][0]["ref_mp"] is None


async def test_duena_confirma_venta_de_mostrador_conservando_vendedor(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    _, _, venta = await _borrador_ab(client, duena, mostrador)
    body = await confirmar_venta(client, duena, venta["id"], [pago("efectivo", 3800)])
    assert body["usuario_id"] == await usuario_id(client, mostrador)
    assert body["confirmada_por_id"] == await usuario_id(client, duena)


async def test_movimiento_registra_a_quien_confirma(client, db_session_factory) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, _, venta = await _borrador_ab(client, duena, mostrador)
    await confirmar_venta(client, duena, venta["id"], [pago("efectivo", 3800)])
    (mov,) = movimientos_de(db_session_factory, a)
    assert mov.usuario_id == await usuario_id(client, duena)


# --- Pagos que igualan el total (RN-VT-04) ---


async def test_pago_incompleto_422_sin_efectos(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3000)])
    assert response.status_code == 422
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


async def test_pago_excedente_422_sin_efectos(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await post_confirmar(client, duena, venta["id"], [pago("efectivo", 4000)])
    assert response.status_code == 422
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


async def test_varios_pagos_cuya_suma_no_iguala_el_total_422(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await post_confirmar(
        client, duena, venta["id"], [pago("efectivo", 1800), pago("tarjeta", 1999.99)]
    )
    assert response.status_code == 422
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


async def test_ref_mp_en_pago_efectivo_422_sin_efectos(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await post_confirmar(
        client, duena, venta["id"], [pago("efectivo", 3800, ref_mp="MP-1")]
    )
    assert response.status_code == 422
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


@pytest.mark.parametrize(
    "pagos",
    [
        [],
        [pago("efectivo", 0)],
        [pago("efectivo", -3800)],
        [pago("efectivo", 3800.123)],
        [pago("cheque", 3800)],
        [pago("efectivo", 633.34)] * 6,
    ],
)
async def test_pagos_invalidos_por_schema_422_sin_efectos(
    client, db_session_factory, pagos
) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await post_confirmar(client, duena, venta["id"], pagos)
    assert response.status_code == 422
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


async def test_ref_mp_ya_registrado_409_con_rollback_total_de_la_segunda_venta(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await crear_producto(client, duena, sku="CF-RM", costo=1000, margen_pct=0.5, stock_actual=5)
    primera = await crear_venta(client, duena, [(a, 1)])
    segunda = await crear_venta(client, duena, [(a, 2)])
    await confirmar_venta(client, duena, primera["id"], [pago("mp", 1500, ref_mp="MP-123")])
    stock_tras_primera = (await get_producto(client, duena, a))["stock_actual"]
    assert stock_tras_primera == 4
    response = await post_confirmar(
        client, duena, segunda["id"], [pago("mp", 3000, ref_mp="MP-123")]
    )
    assert response.status_code == 409
    assert (await get_producto(client, duena, a))["stock_actual"] == 4
    assert len(movimientos_de(db_session_factory, a)) == 1
    assert _pagos_de(db_session_factory, segunda["id"]) == []
    assert _eventos_de(db_session_factory, segunda["id"]) == []
    assert (await get_venta(client, duena, segunda["id"]))["estado"] == "borrador"


# --- RN-VT-01: revalidacion de stock bajo la transaccion ---


async def test_stock_consumido_entre_borrador_y_confirmacion_409(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    p = await crear_producto(client, duena, sku="CF-RV", costo=1000, margen_pct=0.5, stock_actual=2)
    primero = await crear_venta(client, duena, [(p, 2)])
    otra = await crear_venta(client, duena, [(p, 1)])
    await confirmar_venta(client, duena, otra["id"], [pago("efectivo", 1500)])
    response = await post_confirmar(client, duena, primero["id"], [pago("efectivo", 3000)])
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "mensaje": "stock insuficiente",
        "faltantes": [{"producto_id": p, "solicitado": 2, "disponible": 1}],
    }
    assert (await get_producto(client, duena, p))["stock_actual"] == 1
    assert _pagos_de(db_session_factory, primero["id"]) == []
    assert _eventos_de(db_session_factory, primero["id"]) == []
    borrador = await get_venta(client, duena, primero["id"])
    assert borrador["estado"] == "borrador"
    assert len(movimientos_de(db_session_factory, p)) == 1  # solo la otra venta


async def test_faltantes_de_todas_las_lineas_y_ninguna_se_descuenta(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    ok = await crear_producto(client, duena, sku="CF-OK", costo=100, stock_actual=10)
    corto = await crear_producto(client, duena, sku="CF-CT", costo=100, stock_actual=3)
    venta = await crear_venta(client, duena, [(ok, 2), (corto, 3)])
    # Entre el borrador y la confirmacion se agota `corto` y baja `ok` a 1.
    for producto_id, delta in [(corto, -3), (ok, -9)]:
        ajuste = await client.post(
            f"/api/productos/{producto_id}/ajustar",
            json={"cantidad_delta": delta, "motivo": "consumo"},
            headers=duena,
        )
        assert ajuste.status_code == 200
    response = await post_confirmar(client, duena, venta["id"], [pago("efectivo", venta["total"])])
    assert response.status_code == 409
    faltantes = {f["producto_id"]: f for f in response.json()["detail"]["faltantes"]}
    assert faltantes[ok] == {"producto_id": ok, "solicitado": 2, "disponible": 1}
    assert faltantes[corto] == {"producto_id": corto, "solicitado": 3, "disponible": 0}
    assert (await get_producto(client, duena, ok))["stock_actual"] == 1
    assert (await get_producto(client, duena, corto))["stock_actual"] == 0


# --- Propiedad y permisos (D12) ---


async def test_mostrador_no_confirma_venta_ajena_404_sin_cambios(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await post_confirmar(client, mostrador, venta["id"], [pago("efectivo", 3800)])
    assert response.status_code == 404
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


async def test_confirmar_venta_inexistente_404(client) -> None:
    duena = await login_duena(client)
    response = await post_confirmar(client, duena, "no-existe", [pago("efectivo", 100)])
    assert response.status_code == 404


async def test_confirmar_sin_autenticacion_401(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await client.post(
        f"{VENTAS_URL}/{venta['id']}/confirmar", json={"pagos": [pago("efectivo", 3800)]}
    )
    assert response.status_code == 401
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


async def test_contadores_globales_tras_confirmar_dos_ventas(
    client, db_session_factory
) -> None:
    from app.models import EventoOutbox, MovimientoStock, PagoVenta

    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    v1 = await crear_venta(client, duena, [(a, 2)], clave=clave_nueva())
    v2 = await crear_venta(client, duena, [(a, 1), (b, 1)], clave=clave_nueva())
    await confirmar_venta(client, duena, v1["id"], [pago("efectivo", v1["total"])])
    await confirmar_venta(client, duena, v2["id"], [pago("efectivo", 1000), pago("tarjeta", 1300)])
    assert contar(db_session_factory, MovimientoStock) == 3
    assert contar(db_session_factory, PagoVenta) == 3
    assert contar(db_session_factory, EventoOutbox) == 2


# --- Triangulacion (task 6.3) ---


async def test_fallo_en_segunda_linea_revierte_todo(
    client, db_session_factory, monkeypatch
) -> None:
    from app.services import ventas as svc_ventas

    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)

    original = svc_ventas.aplicar_movimiento
    llamadas = []

    def _falla_en_la_segunda(*args, **kwargs):
        llamadas.append(args[2])
        if len(llamadas) == 2:
            raise RuntimeError("falla simulada en la segunda linea")
        return original(*args, **kwargs)

    monkeypatch.setattr(svc_ventas, "aplicar_movimiento", _falla_en_la_segunda)
    # El error no es de dominio: sube como 500 (el cliente de test lo re-lanza).
    with pytest.raises(RuntimeError, match="segunda linea"):
        await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3800)])
    # La primera linea SI llego a aplicarse dentro de la transaccion...
    assert len(llamadas) == 2
    monkeypatch.undo()

    # ...pero nada persiste: stock, movimientos, pagos, evento ni estado.
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])
    # La venta sigue siendo confirmable despues del fallo.
    assert (
        await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3800)])
    ).status_code == 200


async def test_ultima_unidad_secuencial_una_confirma_y_la_otra_409(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    p = await crear_producto(client, duena, sku="CF-UL", costo=1000, margen_pct=0.5, stock_actual=1)
    de_duena = await crear_venta(client, duena, [(p, 1)])
    de_mostrador = await crear_venta(client, mostrador, [(p, 1)])
    primera = await post_confirmar(client, duena, de_duena["id"], [pago("efectivo", 1500)])
    segunda = await post_confirmar(client, mostrador, de_mostrador["id"], [pago("efectivo", 1500)])
    assert (primera.status_code, segunda.status_code) == (200, 409)
    assert (await get_producto(client, duena, p))["stock_actual"] == 0
    assert len(movimientos_de(db_session_factory, p)) == 1
    assert _pagos_de(db_session_factory, de_mostrador["id"]) == []
    assert _eventos_de(db_session_factory, de_mostrador["id"]) == []
    assert (await get_venta(client, duena, de_mostrador["id"]))["estado"] == "borrador"


async def test_mismo_ref_mp_repetido_en_la_misma_request_409_con_rollback(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    response = await post_confirmar(
        client,
        duena,
        venta["id"],
        [pago("mp", 1900, ref_mp="MP-DUP"), pago("mp", 1900, ref_mp="MP-DUP")],
    )
    assert response.status_code == 409
    await _nada_cambio(client, duena, db_session_factory, a, b, venta["id"])


async def test_producto_dado_de_baja_despues_del_borrador_igual_se_confirma(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, b, venta = await _borrador_ab(client, duena, duena)
    assert (await client.delete(f"/api/productos/{b}", headers=duena)).status_code == 204
    response = await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3800)])
    assert response.status_code == 200
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    assert (await get_producto(client, duena, b))["stock_actual"] == 0


async def test_cliente_dado_de_baja_despues_del_borrador_igual_se_confirma(client) -> None:
    from tests.ventas_helpers import crear_cliente

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    cliente_id = await crear_cliente(client, duena)
    venta = await crear_venta(client, duena, [(a, 1)], cliente_id=cliente_id)
    assert (await client.delete(f"/api/clientes/{cliente_id}", headers=duena)).status_code == 204
    response = await post_confirmar(client, duena, venta["id"], [pago("efectivo", 1500)])
    assert response.status_code == 200
    assert response.json()["cliente_id"] == cliente_id


async def test_reintento_del_alta_original_tras_confirmar_200_confirmada_sin_tocar_stock(
    client, db_session_factory
) -> None:
    from tests.ventas_helpers import post_venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    clave = clave_nueva()
    alta = await post_venta(client, duena, [(a, 2)], clave=clave)
    assert alta.status_code == 201
    await confirmar_venta(client, duena, alta.json()["id"], [pago("efectivo", 3000)])
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    reintento = await post_venta(client, duena, [(a, 2)], clave=clave)
    assert reintento.status_code == 200
    assert reintento.json()["id"] == alta.json()["id"]
    assert reintento.json()["estado"] == "confirmada"
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    assert len(movimientos_de(db_session_factory, a)) == 1
