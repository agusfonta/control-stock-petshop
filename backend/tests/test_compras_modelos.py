"""Modelos de compras via ORM (C-07 task 2.1, RED-first).

Cubre spec "Migracion 0006 crea las tablas de compras": checks
(cantidad > 0, costo_unitario > 0, monto > 0), un producto por pedido
en lineas y en entradas, entradas append-only y estado default
pendiente. En RED fallan: PedidoCompra/LineaPedido/EntradaStock/
PagoDistribuidora no existen en app.models.
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from tests.conftest import DUENA_EMAIL


def _base(db_session_factory):
    """Crea usuario(duena)/distribuidora/producto y devuelve sus ids."""
    from app.models import Distribuidora, Producto, Usuario

    with db_session_factory() as session:
        usuario = session.query(Usuario).filter_by(email=DUENA_EMAIL).one()
        distribuidora = Distribuidora(nombre="Distri Sur")
        producto = Producto(sku="CMP-001", nombre="Alimento", costo=1000)
        session.add_all([distribuidora, producto])
        session.commit()
        return usuario.id, distribuidora.id, producto.id


def _pedido(session, uid: str, did: str):
    from app.models import PedidoCompra

    pedido = PedidoCompra(distribuidora_id=did, usuario_id=uid)
    session.add(pedido)
    session.commit()
    return pedido


def test_pedido_estado_default_pendiente_y_activo(
    db_session_factory, seed_users
) -> None:
    uid, did, _ = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        session.refresh(pedido)
        assert pedido.estado == "pendiente"
        assert pedido.activo is True
        assert pedido.notas is None
        assert pedido.recibido_at is None
        assert pedido.recibido_por_id is None
        assert pedido.created_at is not None


@pytest.mark.parametrize("cantidad", [0, -1])
def test_linea_cantidad_no_positiva_rechazada(
    db_session_factory, seed_users, cantidad
) -> None:
    from app.models import LineaPedido

    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        session.add(
            LineaPedido(
                pedido_id=pedido.id,
                producto_id=pid,
                cantidad=cantidad,
                costo_unitario=100,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.parametrize("costo", [0, -5])
def test_linea_costo_no_positivo_rechazado(
    db_session_factory, seed_users, costo
) -> None:
    from app.models import LineaPedido

    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        session.add(
            LineaPedido(
                pedido_id=pedido.id,
                producto_id=pid,
                cantidad=1,
                costo_unitario=costo,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_linea_valida_persiste(db_session_factory, seed_users) -> None:
    from app.models import LineaPedido

    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        linea = LineaPedido(
            pedido_id=pedido.id, producto_id=pid, cantidad=10, costo_unitario=800
        )
        session.add(linea)
        session.commit()
        session.refresh(linea)
        assert linea.id
        assert linea.cantidad == 10
        assert linea.costo_unitario == 800


def test_producto_repetido_en_pedido_rechazado(
    db_session_factory, seed_users
) -> None:
    from app.models import LineaPedido

    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        session.add(
            LineaPedido(
                pedido_id=pedido.id, producto_id=pid, cantidad=1, costo_unitario=100
            )
        )
        session.commit()
        session.add(
            LineaPedido(
                pedido_id=pedido.id, producto_id=pid, cantidad=2, costo_unitario=100
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_mismo_producto_en_pedidos_distintos_permitido(
    db_session_factory, seed_users
) -> None:
    from app.models import LineaPedido

    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        for _ in range(2):
            pedido = _pedido(session, uid, did)
            session.add(
                LineaPedido(
                    pedido_id=pedido.id,
                    producto_id=pid,
                    cantidad=1,
                    costo_unitario=100,
                )
            )
        session.commit()
        assert session.query(LineaPedido).count() == 2


def _entrada(pedido_id, pid, uid, **overrides):
    from app.models import EntradaStock

    datos = dict(
        pedido_id=pedido_id,
        producto_id=pid,
        cantidad=10,
        costo_unitario=800,
        usuario_id=uid,
    )
    datos.update(overrides)
    return EntradaStock(**datos)


def test_entrada_valida_persiste_con_created_at(
    db_session_factory, seed_users
) -> None:
    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        entrada = _entrada(pedido.id, pid, uid)
        session.add(entrada)
        session.commit()
        session.refresh(entrada)
        assert entrada.id
        assert entrada.cantidad == 10
        assert entrada.costo_unitario == 800
        assert entrada.created_at is not None


def test_entrada_duplicada_pedido_producto_rechazada(
    db_session_factory, seed_users
) -> None:
    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        session.add(_entrada(pedido.id, pid, uid))
        session.commit()
        session.add(_entrada(pedido.id, pid, uid, cantidad=3))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_entrada_cantidad_cero_rechazada(db_session_factory, seed_users) -> None:
    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        session.add(_entrada(pedido.id, pid, uid, cantidad=0))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_entrada_update_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import EntradaStock

    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        entrada = _entrada(pedido.id, pid, uid)
        session.add(entrada)
        session.commit()
        entrada_id = entrada.id
    with db_session_factory() as session:
        entrada = session.get(EntradaStock, entrada_id)
        entrada.cantidad = 99
        with pytest.raises(InvalidRequestError):
            session.commit()
        session.rollback()
        assert session.get(EntradaStock, entrada_id).cantidad == 10


def test_entrada_delete_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import EntradaStock

    uid, did, pid = _base(db_session_factory)
    with db_session_factory() as session:
        pedido = _pedido(session, uid, did)
        entrada = _entrada(pedido.id, pid, uid)
        session.add(entrada)
        session.commit()
        entrada_id = entrada.id
    with db_session_factory() as session:
        session.delete(session.get(EntradaStock, entrada_id))
        with pytest.raises(InvalidRequestError):
            session.commit()
        session.rollback()
        assert session.get(EntradaStock, entrada_id) is not None


@pytest.mark.parametrize("monto", [0, -100])
def test_pago_monto_no_positivo_rechazado(
    db_session_factory, seed_users, monto
) -> None:
    from app.models import PagoDistribuidora

    uid, did, _ = _base(db_session_factory)
    with db_session_factory() as session:
        session.add(
            PagoDistribuidora(
                distribuidora_id=did, monto=monto, metodo="efectivo", usuario_id=uid
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_pago_valido_default_fecha_hoy_y_activo(
    db_session_factory, seed_users
) -> None:
    from app.models import PagoDistribuidora

    uid, did, _ = _base(db_session_factory)
    with db_session_factory() as session:
        pago = PagoDistribuidora(
            distribuidora_id=did,
            monto=5000,
            metodo="transferencia",
            usuario_id=uid,
        )
        session.add(pago)
        session.commit()
        session.refresh(pago)
        assert pago.fecha == date.today()
        assert pago.activo is True
        assert pago.monto == 5000
        assert pago.nota is None
