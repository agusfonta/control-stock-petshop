"""Humo de los helpers de reportes (C-14 task 5.1): importan y hacen lo que dicen."""

from datetime import date

from tests.reportes_helpers import (
    crear_producto,
    fijar_ahora,
    fijar_confirmada_at,
    login_duena,
    pago,
    utc,
    venta_confirmada_en,
)


async def test_venta_confirmada_en_mueve_confirmada_at(client, db_session_factory) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a = await crear_producto(client, duena, sku="RH-A", costo=1000, margen_pct=0.5, stock_actual=3)
    venta = await venta_confirmada_en(
        client, duena, db_session_factory, [(a, 1)], [pago(monto=1500)], utc(2026, 10, 6, 2, 30)
    )
    with db_session_factory() as session:
        guardada = session.get(Venta, venta["id"])
        assert guardada.estado == "confirmada"
        assert guardada.confirmada_at.replace(tzinfo=None) == utc(2026, 10, 6, 2, 30).replace(
            tzinfo=None
        )
    fijar_confirmada_at(db_session_factory, venta["id"], utc(2026, 10, 7, 3, 0))
    with db_session_factory() as session:
        assert session.get(Venta, venta["id"]).confirmada_at.replace(tzinfo=None) == utc(
            2026, 10, 7, 3, 0
        ).replace(tzinfo=None)


def test_fijar_ahora_controla_hoy(monkeypatch) -> None:
    from app.services import reportes

    fijar_ahora(monkeypatch, utc(2026, 10, 7, 1, 0))
    assert reportes.hoy() == date(2026, 10, 6)
