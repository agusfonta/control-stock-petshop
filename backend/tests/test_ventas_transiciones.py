"""Transiciones idempotentes de venta (C-10 task 7.1, RED-first, D6/D9).

Solo borrador -> confirmada y confirmada -> anulada. Repetir una transicion
ya hecha es replay: 200 sin efectos (mismos pagos al confirmar; anular una
anulada). Confirmar con pagos distintos, confirmar una anulada y anular un
borrador son 409 sin efectos. En RED fallan: hoy el segundo confirmar es
409 (minimo de 6.2) y anular no existe.
"""

from datetime import datetime, timezone

from tests.ventas_helpers import (
    confirmar_venta,
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
)


def _pagos_de(db_session_factory, venta_id: str) -> list:
    from app.models import PagoVenta

    with db_session_factory() as session:
        return session.query(PagoVenta).filter_by(venta_id=venta_id).all()


async def _venta_a(client, duena, headers=None, stock=5):
    """Producto A (1500, stock `stock`) y borrador de 2 unidades (total 3000)."""
    a = await crear_producto(client, duena, sku="TR-A", costo=1000, margen_pct=0.5, stock_actual=stock)
    venta = await crear_venta(client, headers or duena, [(a, 2)])
    assert venta["total"] == 3000
    return a, venta


async def test_confirmar_dos_veces_con_los_mismos_pagos_200_y_200_sin_efectos(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, venta = await _venta_a(client, duena)
    pagos = [pago("efectivo", 1000), pago("mp", 2000, ref_mp="MP-1")]
    primera = await post_confirmar(client, duena, venta["id"], pagos)
    stock = (await get_producto(client, duena, a))["stock_actual"]
    movimientos = len(movimientos_de(db_session_factory, a))
    pagos_db = len(_pagos_de(db_session_factory, venta["id"]))
    segunda = await post_confirmar(client, duena, venta["id"], pagos)
    assert (primera.status_code, segunda.status_code) == (200, 200)
    assert segunda.json()["estado"] == "confirmada"
    assert segunda.json()["confirmada_at"] == primera.json()["confirmada_at"]
    assert (stock, movimientos, pagos_db) == (3, 1, 2)
    assert (await get_producto(client, duena, a))["stock_actual"] == stock
    assert len(movimientos_de(db_session_factory, a)) == movimientos
    assert len(_pagos_de(db_session_factory, venta["id"])) == pagos_db
    assert sorted(p["id"] for p in segunda.json()["pagos"]) == sorted(
        p["id"] for p in primera.json()["pagos"]
    )


async def test_reconfirmar_con_los_mismos_pagos_en_otro_orden_es_replay_200(client) -> None:
    duena = await login_duena(client)
    _, venta = await _venta_a(client, duena)
    await confirmar_venta(
        client, duena, venta["id"], [pago("efectivo", 1000), pago("tarjeta", 2000)]
    )
    again = await post_confirmar(
        client, duena, venta["id"], [pago("tarjeta", 2000), pago("efectivo", 1000)]
    )
    assert again.status_code == 200


async def test_reconfirmar_con_pagos_distintos_409_conservando_los_originales(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, venta = await _venta_a(client, duena)
    await confirmar_venta(client, duena, venta["id"], [pago("efectivo", 3000)])
    for otros in (
        [pago("efectivo", 1000), pago("tarjeta", 2000)],  # otro reparto, misma suma
        [pago("transferencia", 3000)],  # otro metodo
    ):
        response = await post_confirmar(client, duena, venta["id"], otros)
        assert response.status_code == 409
    (original,) = _pagos_de(db_session_factory, venta["id"])
    assert (original.metodo, float(original.monto)) == ("efectivo", 3000.0)
    assert (await get_producto(client, duena, a))["stock_actual"] == 3
    assert len(movimientos_de(db_session_factory, a)) == 1


async def test_replay_conserva_al_usuario_que_confirmo_primero(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    _, venta = await _venta_a(client, duena, headers=mostrador)
    primera = await confirmar_venta(client, mostrador, venta["id"], [pago("efectivo", 3000)])
    replay = await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3000)])
    assert replay.status_code == 200
    assert replay.json()["confirmada_por_id"] == await usuario_id(client, mostrador)
    assert replay.json()["confirmada_at"] == primera["confirmada_at"]


async def test_confirmar_una_venta_anulada_409_sin_cambios_de_stock(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, venta = await _venta_a(client, duena)
    ahora = datetime.now(timezone.utc)
    with db_session_factory() as session:
        fila = session.get(Venta, venta["id"])
        fila.estado = "anulada"
        fila.confirmada_at = ahora
        fila.anulada_at = ahora
        fila.motivo_anulacion = "anulada para el test"
        session.commit()
    response = await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3000)])
    assert response.status_code == 409
    assert (await get_producto(client, duena, a))["stock_actual"] == 5
    assert movimientos_de(db_session_factory, a) == []
    assert _pagos_de(db_session_factory, venta["id"]) == []
    assert (await get_venta(client, duena, venta["id"]))["estado"] == "anulada"


async def test_anular_un_borrador_409_y_sigue_en_borrador(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a, venta = await _venta_a(client, duena)
    response = await post_anular(client, duena, venta["id"])
    assert response.status_code == 409
    assert (await get_venta(client, duena, venta["id"]))["estado"] == "borrador"
    assert (await get_producto(client, duena, a))["stock_actual"] == 5
    assert movimientos_de(db_session_factory, a) == []


async def test_confirmar_dos_veces_y_anular_dos_veces_aplica_un_solo_movimiento_de_cada_signo(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a, venta = await _venta_a(client, duena)
    for _ in range(2):
        assert (
            await post_confirmar(client, duena, venta["id"], [pago("efectivo", 3000)])
        ).status_code == 200
    for _ in range(2):
        assert (await post_anular(client, duena, venta["id"])).status_code == 200
    assert (await get_producto(client, duena, a))["stock_actual"] == 5
    assert [m.cantidad for m in movimientos_de(db_session_factory, a)] == [-2, 2]
