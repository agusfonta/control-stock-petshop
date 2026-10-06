"""Anular venta solo por duena con movimiento inverso (C-10 task 8.1, RED-first).

POST /api/ventas/{id}/anular (RN-VT-03, D3/D13): devuelve el stock de cada
linea con un movimiento tipo `venta` de cantidad POSITIVA (ref_id a la
venta, motivo de anulacion), sin tocar los movimientos originales ni los
pagos, y registra el evento `venta.anulada`. En RED fallan: el endpoint
anular no existe (404/405).
"""

import pytest

from tests.ventas_helpers import (
    VENTAS_URL,
    contar,
    crear_producto,
    crear_venta,
    get_producto,
    get_venta,
    login_duena,
    login_mostrador,
    movimientos_de,
    pago,
    post_anular,
    post_confirmar,
    usuario_id,
    venta_confirmada,
)


def _eventos_de(db_session_factory, venta_id: str) -> list:
    from app.models import EventoOutbox

    with db_session_factory() as session:
        return (
            session.query(EventoOutbox)
            .filter_by(agregado_id=venta_id)
            .order_by(EventoOutbox.tipo)
            .all()
        )


def _pagos_de(db_session_factory, venta_id: str) -> list:
    from app.models import PagoVenta

    with db_session_factory() as session:
        return session.query(PagoVenta).filter_by(venta_id=venta_id).all()


async def _confirmada_2a(client, duena, headers=None):
    """Venta confirmada de 2xA (stock 5 -> 3), total 3000 en efectivo."""
    a = await crear_producto(client, duena, sku="AN-A", costo=1000, margen_pct=0.5, stock_actual=5)
    venta = await venta_confirmada(
        client, headers or duena, [(a, 2)], [pago("efectivo", 3000)]
    )
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    return a, venta


async def test_duena_anula_y_devuelve_stock_con_movimiento_inverso(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, venta = await _confirmada_2a(client, duena)
    response = await post_anular(client, duena, venta["id"], "cliente se arrepintio")
    assert response.status_code == 200
    body = response.json()
    assert body["estado"] == "anulada"
    assert body["motivo_anulacion"] == "cliente se arrepintio"
    assert (await get_producto(client, duena, a))["stock_actual"] == 5

    original, inverso = movimientos_de(db_session_factory, a)
    # El movimiento original sigue intacto (ledger append-only).
    assert (original.tipo, original.cantidad) == ("venta", -2)
    assert (original.stock_previo, original.stock_nuevo) == (5, 3)
    assert original.ref_id == venta["id"]
    # El inverso es tipo `venta` con cantidad POSITIVA (D3), auditable.
    assert (inverso.tipo, inverso.cantidad) == ("venta", 2)
    assert (inverso.stock_previo, inverso.stock_nuevo) == (3, 5)
    assert inverso.ref_id == venta["id"]
    assert inverso.usuario_id == await usuario_id(client, duena)
    assert "anulacion" in inverso.motivo
    assert venta["id"] in inverso.motivo
    assert "cliente se arrepintio" in inverso.motivo


async def test_anular_registra_auditoria_conserva_pagos_y_crea_evento(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    _, venta = await _confirmada_2a(client, duena)
    body = (await post_anular(client, duena, venta["id"])).json()
    assert body["anulada_at"] is not None
    assert body["anulada_por_id"] == await usuario_id(client, duena)
    assert body["confirmada_at"] == venta["confirmada_at"]
    # Sin devolucion de dinero (D13): los pagos quedan tal cual.
    assert [(p["metodo"], p["monto"]) for p in body["pagos"]] == [("efectivo", 3000)]
    (pago_db,) = _pagos_de(db_session_factory, venta["id"])
    assert float(pago_db.monto) == 3000.0
    tipos = [e.tipo for e in _eventos_de(db_session_factory, venta["id"])]
    assert tipos == ["venta.anulada", "venta.confirmada"]
    anulada = [e for e in _eventos_de(db_session_factory, venta["id"]) if e.tipo == "venta.anulada"]
    assert anulada[0].procesado_at is None


async def test_duena_anula_venta_de_un_mostrador(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, venta = await _confirmada_2a(client, duena, headers=mostrador)
    response = await post_anular(client, duena, venta["id"])
    assert response.status_code == 200
    assert response.json()["usuario_id"] == await usuario_id(client, mostrador)
    assert (await get_producto(client, duena, a))["stock_actual"] == 5


async def test_mostrador_no_puede_anular_ni_su_propia_venta_403_sin_cambios(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, venta = await _confirmada_2a(client, duena, headers=mostrador)
    response = await post_anular(client, mostrador, venta["id"])
    assert response.status_code == 403
    assert (await get_venta(client, duena, venta["id"]))["estado"] == "confirmada"
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    assert len(movimientos_de(db_session_factory, a)) == 1
    assert [e.tipo for e in _eventos_de(db_session_factory, venta["id"])] == ["venta.confirmada"]


@pytest.mark.parametrize("cuerpo", [{}, {"motivo": ""}, {"motivo": "   "}, {"motivo": None}])
async def test_anular_sin_motivo_o_en_blanco_422_y_sigue_confirmada(
    client, db_session_factory, cuerpo
) -> None:
    duena = await login_duena(client)
    a, venta = await _confirmada_2a(client, duena)
    response = await client.post(
        f"{VENTAS_URL}/{venta['id']}/anular", json=cuerpo, headers=duena
    )
    assert response.status_code == 422
    assert (await get_venta(client, duena, venta["id"]))["estado"] == "confirmada"
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    assert len(movimientos_de(db_session_factory, a)) == 1


async def test_anular_dos_veces_200_y_200_sin_segunda_devolucion(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, venta = await _confirmada_2a(client, duena)
    primera = await post_anular(client, duena, venta["id"], "primer motivo")
    segunda = await post_anular(client, duena, venta["id"], "otro motivo")
    assert (primera.status_code, segunda.status_code) == (200, 200)
    assert segunda.json()["estado"] == "anulada"
    # El replay no pisa la auditoria de la primera anulacion.
    assert segunda.json()["motivo_anulacion"] == "primer motivo"
    assert segunda.json()["anulada_at"] == primera.json()["anulada_at"]
    assert (await get_producto(client, duena, a))["stock_actual"] == 5
    assert len(movimientos_de(db_session_factory, a)) == 2
    tipos = [e.tipo for e in _eventos_de(db_session_factory, venta["id"])]
    assert tipos == ["venta.anulada", "venta.confirmada"]


async def test_anular_venta_inexistente_404(client) -> None:
    duena = await login_duena(client)
    response = await post_anular(client, duena, "no-existe")
    assert response.status_code == 404


async def test_anular_sin_autenticacion_401(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, venta = await _confirmada_2a(client, duena)
    response = await client.post(
        f"{VENTAS_URL}/{venta['id']}/anular", json={"motivo": "x"}
    )
    assert response.status_code == 401
    assert (await get_venta(client, duena, venta["id"]))["estado"] == "confirmada"
    assert len(movimientos_de(db_session_factory, a)) == 1


async def test_anular_devuelve_el_stock_de_todas_las_lineas(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await crear_producto(client, duena, sku="AN-M1", costo=1000, margen_pct=0.5, stock_actual=5)
    b = await crear_producto(client, duena, sku="AN-M2", costo=800, margen_pct=0, stock_actual=1)
    venta = await venta_confirmada(client, duena, [(a, 2), (b, 1)], [pago("tarjeta", 3800)])
    assert (await post_anular(client, duena, venta["id"])).status_code == 200
    assert (await get_producto(client, duena, a))["stock_actual"] == 5
    assert (await get_producto(client, duena, b))["stock_actual"] == 1
    assert [m.cantidad for m in movimientos_de(db_session_factory, b)] == [-1, 1]


# --- Triangulacion (task 8.3) ---


async def test_anular_con_producto_dado_de_baja_devuelve_stock(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, venta = await _confirmada_2a(client, duena)
    assert (await client.delete(f"/api/productos/{a}", headers=duena)).status_code == 204
    response = await post_anular(client, duena, venta["id"])
    assert response.status_code == 200
    assert (await get_producto(client, duena, a))["stock_actual"] == 5


async def test_fallo_en_segunda_linea_de_la_anulacion_revierte_todo(
    client, db_session_factory, monkeypatch
) -> None:
    from app.services import ventas as svc_ventas

    duena = await login_duena(client)
    a = await crear_producto(client, duena, sku="AN-R1", costo=1000, margen_pct=0.5, stock_actual=5)
    b = await crear_producto(client, duena, sku="AN-R2", costo=800, margen_pct=0, stock_actual=3)
    venta = await venta_confirmada(client, duena, [(a, 2), (b, 1)], [pago("efectivo", 3800)])

    original = svc_ventas.aplicar_movimiento
    llamadas = []

    def _falla_en_la_segunda(*args, **kwargs):
        llamadas.append(args[2])
        if len(llamadas) == 2:
            raise RuntimeError("falla simulada en la segunda linea")
        return original(*args, **kwargs)

    monkeypatch.setattr(svc_ventas, "aplicar_movimiento", _falla_en_la_segunda)
    with pytest.raises(RuntimeError, match="segunda linea"):
        await post_anular(client, duena, venta["id"])
    assert len(llamadas) == 2
    monkeypatch.undo()

    # Sigue confirmada, sin stock devuelto, sin evento de anulacion.
    estado = await get_venta(client, duena, venta["id"])
    assert estado["estado"] == "confirmada"
    assert estado["anulada_at"] is None and estado["motivo_anulacion"] is None
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    assert (await get_producto(client, duena, b))["stock_actual"] == 2
    assert len(movimientos_de(db_session_factory, a)) == 1
    assert len(movimientos_de(db_session_factory, b)) == 1
    assert [e.tipo for e in _eventos_de(db_session_factory, venta["id"])] == ["venta.confirmada"]
    # Y la anulacion sigue siendo posible despues del fallo.
    assert (await post_anular(client, duena, venta["id"])).status_code == 200


async def test_suma_de_movimientos_venta_tras_vender_y_anular_es_cero(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await crear_producto(client, duena, sku="AN-SM", costo=1000, margen_pct=0.5, stock_actual=9)
    v1 = await venta_confirmada(client, duena, [(a, 4)], [pago("efectivo", 6000)])
    v2 = await venta_confirmada(client, duena, [(a, 3)], [pago("efectivo", 4500)])
    assert (await get_producto(client, duena, a))["stock_actual"] == 2
    await post_anular(client, duena, v1["id"])
    await post_anular(client, duena, v2["id"])
    assert (await get_producto(client, duena, a))["stock_actual"] == 9
    movimientos = movimientos_de(db_session_factory, a)
    assert sum(m.cantidad for m in movimientos if m.tipo == "venta") == 0
    assert len(movimientos) == 4


async def test_no_se_puede_confirmar_una_venta_recien_anulada(client) -> None:
    duena = await login_duena(client)
    a, venta = await _confirmada_2a(client, duena)
    await post_anular(client, duena, venta["id"])
    response = await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3000)])
    assert response.status_code == 409
    assert (await get_producto(client, duena, a))["stock_actual"] == 5


async def test_borrador_sin_confirmar_no_cuenta_para_la_anulacion(client, db_session_factory) -> None:
    from app.models import MovimientoStock

    duena = await login_duena(client)
    a = await crear_producto(client, duena, sku="AN-BR", costo=1000, margen_pct=0.5, stock_actual=5)
    borrador = await crear_venta(client, duena, [(a, 1)])
    assert (await post_anular(client, duena, borrador["id"])).status_code == 409
    assert contar(db_session_factory, MovimientoStock) == 0
