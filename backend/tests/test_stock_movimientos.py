"""MovimientoStock append-only via ORM (C-05 task 1.1, RED-first).

Cubre spec scenarios: ajuste genera movimiento con previo/nuevo,
cantidad negativa, historial ordenado, check stock_nuevo >= 0 a nivel
base, y bloqueo de update/delete (append-only real, decision D7).
En RED estos tests fallan: MovimientoStock no existe en app.models.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from tests.conftest import DUENA_EMAIL


def _usuario_id(db_session_factory):
    from app.models import Usuario

    with db_session_factory() as session:
        user = session.query(Usuario).filter_by(email=DUENA_EMAIL).one()
        return user.id


def _producto_id(db_session_factory):
    from app.models import Producto

    with db_session_factory() as session:
        producto = Producto(
            sku="STK-001",
            nombre="Alimento Perro 20kg",
            costo=1000,
            margen_pct=0.5,
            stock_actual=10,
            stock_minimo=2,
        )
        session.add(producto)
        session.commit()
        return producto.id


def test_insert_movimiento_persiste_previo_nuevo_y_usuario(
    db_session_factory, seed_users
) -> None:
    from app.models import MovimientoStock

    uid = _usuario_id(db_session_factory)
    pid = _producto_id(db_session_factory)
    with db_session_factory() as session:
        mov = MovimientoStock(
            producto_id=pid,
            tipo="ajuste",
            cantidad=5,
            stock_previo=10,
            stock_nuevo=15,
            motivo="conteo fisico",
            usuario_id=uid,
        )
        session.add(mov)
        session.commit()
        session.refresh(mov)
        assert mov.id
        assert mov.producto_id == pid
        assert mov.tipo == "ajuste"
        assert mov.cantidad == 5
        assert mov.stock_previo == 10
        assert mov.stock_nuevo == 15
        assert mov.usuario_id == uid
        assert mov.created_at is not None


def test_insert_movimiento_cantidad_negativa(
    db_session_factory, seed_users
) -> None:
    from app.models import MovimientoStock

    uid = _usuario_id(db_session_factory)
    pid = _producto_id(db_session_factory)
    with db_session_factory() as session:
        mov = MovimientoStock(
            producto_id=pid,
            tipo="ajuste",
            cantidad=-3,
            stock_previo=10,
            stock_nuevo=7,
            motivo="rotura",
            usuario_id=uid,
        )
        session.add(mov)
        session.commit()
        session.refresh(mov)
        assert mov.cantidad == -3
        assert mov.stock_previo == 10
        assert mov.stock_nuevo == 7


def test_update_movimiento_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import MovimientoStock

    uid = _usuario_id(db_session_factory)
    pid = _producto_id(db_session_factory)
    with db_session_factory() as session:
        mov = MovimientoStock(
            producto_id=pid,
            tipo="ajuste",
            cantidad=5,
            stock_previo=10,
            stock_nuevo=15,
            motivo="conteo fisico",
            usuario_id=uid,
        )
        session.add(mov)
        session.commit()
        mov_id = mov.id
    with db_session_factory() as session:
        mov = session.get(MovimientoStock, mov_id)
        mov.cantidad = 99
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


def test_delete_movimiento_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import MovimientoStock

    uid = _usuario_id(db_session_factory)
    pid = _producto_id(db_session_factory)
    with db_session_factory() as session:
        mov = MovimientoStock(
            producto_id=pid,
            tipo="ajuste",
            cantidad=5,
            stock_previo=10,
            stock_nuevo=15,
            motivo="conteo fisico",
            usuario_id=uid,
        )
        session.add(mov)
        session.commit()
        mov_id = mov.id
    with db_session_factory() as session:
        mov = session.get(MovimientoStock, mov_id)
        session.delete(mov)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


def test_check_stock_nuevo_no_negativo_a_nivel_base(
    db_session_factory, seed_users
) -> None:
    from app.models import MovimientoStock

    uid = _usuario_id(db_session_factory)
    pid = _producto_id(db_session_factory)
    with db_session_factory() as session:
        mov = MovimientoStock(
            producto_id=pid,
            tipo="ajuste",
            cantidad=-99,
            stock_previo=10,
            stock_nuevo=-1,
            motivo="invalido",
            usuario_id=uid,
        )
        session.add(mov)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_historial_ordenado_por_created_at(
    db_session_factory, seed_users
) -> None:
    from app.models import MovimientoStock

    uid = _usuario_id(db_session_factory)
    pid = _producto_id(db_session_factory)
    base = datetime(2026, 1, 1, 12, 0, 0)
    with db_session_factory() as session:
        for i, delta in enumerate((2, -1, 4)):
            session.add(
                MovimientoStock(
                    producto_id=pid,
                    tipo="ajuste",
                    cantidad=delta,
                    stock_previo=10,
                    stock_nuevo=10 + delta,
                    motivo=f"ajuste {i}",
                    usuario_id=uid,
                    created_at=base + timedelta(seconds=i),
                )
            )
        session.commit()
    with db_session_factory() as session:
        historial = (
            session.query(MovimientoStock)
            .filter_by(producto_id=pid)
            .order_by(MovimientoStock.created_at.asc())
            .all()
        )
        assert [m.cantidad for m in historial] == [2, -1, 4]
        primero = historial[0]
        assert primero.producto_id == pid
        assert primero.tipo == "ajuste"
        assert primero.stock_previo == 10
        assert primero.stock_nuevo == 12
