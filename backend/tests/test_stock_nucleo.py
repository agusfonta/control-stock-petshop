"""Nucleo sin commit aplicar_movimiento() (C-07 task 1.2, RED-first).

Cubre design D3: el nucleo muta stock + agrega movimiento con flush pero
SIN commit/rollback (el dueno de la transaccion es el llamador), asi la
recepcion de un pedido agrupa N movimientos en una sola transaccion.
En RED fallan: aplicar_movimiento no existe en app.services.stock.
"""

import pytest

from tests.conftest import DUENA_EMAIL


def _usuario(session):
    from app.models import Usuario

    return session.query(Usuario).filter_by(email=DUENA_EMAIL).one()


def _producto(session, sku: str, stock: int = 10):
    from app.models import Producto

    producto = Producto(
        sku=sku,
        nombre=f"Producto {sku}",
        costo=1000,
        margen_pct=0.5,
        stock_actual=stock,
        stock_minimo=2,
    )
    session.add(producto)
    session.commit()
    return producto


def _stock_y_movimientos(db_session_factory, producto_id: str):
    from app.models import MovimientoStock, Producto

    with db_session_factory() as session:
        stock = session.get(Producto, producto_id).stock_actual
        movs = session.query(MovimientoStock).filter_by(producto_id=producto_id).all()
        return stock, movs


def test_nucleo_no_hace_commit_rollback_del_llamador_revierte_todo(
    db_session_factory, seed_users
) -> None:
    from app.services.stock import aplicar_movimiento

    with db_session_factory() as session:
        usuario = _usuario(session)
        pid = _producto(session, "NUC-001", stock=10).id
        producto, movimiento = aplicar_movimiento(
            session, pid, 5, "entrada", usuario, motivo="recepcion"
        )
        # Dentro de la transaccion ya se ve el efecto...
        assert producto.stock_actual == 15
        assert movimiento.stock_previo == 10
        assert movimiento.stock_nuevo == 15
        # ...pero el llamador decide: rollback => nada persiste.
        session.rollback()
    stock, movs = _stock_y_movimientos(db_session_factory, pid)
    assert stock == 10
    assert movs == []


def test_nucleo_dos_llamadas_un_solo_commit_persisten_ambas(
    db_session_factory, seed_users
) -> None:
    from app.services.stock import aplicar_movimiento

    with db_session_factory() as session:
        usuario = _usuario(session)
        pid_a = _producto(session, "NUC-002", stock=3).id
        pid_b = _producto(session, "NUC-003", stock=0).id
        aplicar_movimiento(session, pid_a, 10, "entrada", usuario)
        aplicar_movimiento(session, pid_b, 4, "entrada", usuario)
        session.commit()
    stock_a, movs_a = _stock_y_movimientos(db_session_factory, pid_a)
    stock_b, movs_b = _stock_y_movimientos(db_session_factory, pid_b)
    assert (stock_a, stock_b) == (13, 4)
    assert len(movs_a) == 1 and len(movs_b) == 1


def test_nucleo_persiste_ref_id_y_tipo_entrada(
    db_session_factory, seed_users
) -> None:
    from app.services.stock import aplicar_movimiento

    with db_session_factory() as session:
        usuario = _usuario(session)
        pid = _producto(session, "NUC-004").id
        _, movimiento = aplicar_movimiento(
            session, pid, 2, "entrada", usuario, motivo="m", ref_id="entrada-123"
        )
        session.commit()
        session.refresh(movimiento)
        assert movimiento.tipo == "entrada"
        assert movimiento.ref_id == "entrada-123"
        assert movimiento.motivo == "m"
        assert movimiento.usuario_id == usuario.id


def test_nucleo_ref_id_y_motivo_son_opcionales(
    db_session_factory, seed_users
) -> None:
    from app.services.stock import aplicar_movimiento

    with db_session_factory() as session:
        usuario = _usuario(session)
        pid = _producto(session, "NUC-005").id
        _, movimiento = aplicar_movimiento(session, pid, 1, "entrada", usuario)
        session.commit()
        session.refresh(movimiento)
        assert movimiento.ref_id is None
        assert movimiento.motivo is None


def test_nucleo_delta_cero_levanta_stock_error(
    db_session_factory, seed_users
) -> None:
    from app.services.stock import StockError, aplicar_movimiento

    with db_session_factory() as session:
        usuario = _usuario(session)
        pid = _producto(session, "NUC-006").id
        with pytest.raises(StockError):
            aplicar_movimiento(session, pid, 0, "entrada", usuario)
    stock, movs = _stock_y_movimientos(db_session_factory, pid)
    assert stock == 10
    assert movs == []


def test_nucleo_stock_negativo_levanta_y_no_muta(
    db_session_factory, seed_users
) -> None:
    from app.models import Producto
    from app.services.stock import StockNegativo, aplicar_movimiento

    with db_session_factory() as session:
        usuario = _usuario(session)
        pid = _producto(session, "NUC-007", stock=2).id
        with pytest.raises(StockNegativo):
            aplicar_movimiento(session, pid, -5, "ajuste", usuario, motivo="x")
        # El producto no fue mutado en la sesion del llamador.
        assert session.get(Producto, pid).stock_actual == 2
    stock, movs = _stock_y_movimientos(db_session_factory, pid)
    assert stock == 2
    assert movs == []


def test_nucleo_producto_inexistente_levanta(
    db_session_factory, seed_users
) -> None:
    from app.services.stock import ProductoNoEncontrado, aplicar_movimiento

    with db_session_factory() as session:
        usuario = _usuario(session)
        with pytest.raises(ProductoNoEncontrado):
            aplicar_movimiento(session, "no-existe", 1, "entrada", usuario)
