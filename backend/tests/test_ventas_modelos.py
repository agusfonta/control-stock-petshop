"""Modelos de ventas via ORM (C-10 task 2.1, RED-first).

Cubre spec "Migracion 0007 crea las tablas de ventas": checks
(cantidad > 0, precio_unit > 0, subtotal > 0, monto > 0, total > 0),
un producto por venta, una clave de idempotencia por vendedor, un ref_mp
por pago, ref_mp solo en pagos mp, fechas segun el estado, un evento por
venta y tipo, y lineas/pagos inmutables. En RED fallan: Venta/LineaVenta/
PagoVenta/EventoOutbox no existen en app.models.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from tests.conftest import DUENA_EMAIL, MOSTRADOR_EMAIL


def _base(db_session_factory):
    """Crea usuarios (duena, mostrador) y un producto; devuelve sus ids."""
    from app.models import Producto, Usuario

    with db_session_factory() as session:
        duena = session.query(Usuario).filter_by(email=DUENA_EMAIL).one()
        mostrador = session.query(Usuario).filter_by(email=MOSTRADOR_EMAIL).one()
        producto = Producto(sku="VTA-001", nombre="Alimento", costo=1000)
        session.add(producto)
        session.commit()
        return duena.id, mostrador.id, producto.id


def _venta(session, uid: str, **overrides):
    from app.models import Venta

    datos = dict(usuario_id=uid, total=3000, idempotency_key=str(uuid.uuid4()))
    datos.update(overrides)
    venta = Venta(**datos)
    session.add(venta)
    session.commit()
    return venta


def _linea(venta_id, pid, **overrides):
    from app.models import LineaVenta

    datos = dict(
        venta_id=venta_id,
        producto_id=pid,
        cantidad=2,
        precio_unit=1500,
        subtotal=3000,
    )
    datos.update(overrides)
    return LineaVenta(**datos)


def _pago(venta_id, **overrides):
    from app.models import PagoVenta

    datos = dict(venta_id=venta_id, metodo="efectivo", monto=3000)
    datos.update(overrides)
    return PagoVenta(**datos)


# --- Venta ---


def test_venta_estado_default_borrador_y_activo(db_session_factory, seed_users) -> None:
    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        session.refresh(venta)
        assert venta.estado == "borrador"
        assert venta.activo is True
        assert venta.cliente_id is None
        assert venta.confirmada_at is None
        assert venta.confirmada_por_id is None
        assert venta.anulada_at is None
        assert venta.motivo_anulacion is None
        assert venta.created_at is not None


@pytest.mark.parametrize("total", [0, -1])
def test_venta_total_no_positivo_rechazado(
    db_session_factory, seed_users, total
) -> None:
    from app.models import Venta

    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        session.add(
            Venta(usuario_id=uid, total=total, idempotency_key=str(uuid.uuid4()))
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_venta_confirmada_sin_confirmada_at_rechazada(
    db_session_factory, seed_users
) -> None:
    from app.models import Venta

    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        session.add(
            Venta(
                usuario_id=uid,
                total=100,
                idempotency_key=str(uuid.uuid4()),
                estado="confirmada",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_venta_confirmada_con_confirmada_at_persiste(
    db_session_factory, seed_users
) -> None:
    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(
            session,
            uid,
            estado="confirmada",
            confirmada_at=datetime.now(timezone.utc),
            confirmada_por_id=uid,
        )
        session.refresh(venta)
        assert venta.estado == "confirmada"


@pytest.mark.parametrize(
    "extra",
    [
        {},  # sin anulada_at ni motivo
        {"anulada_at": datetime.now(timezone.utc)},  # sin motivo
        {"motivo_anulacion": "se arrepintio"},  # sin anulada_at
    ],
)
def test_venta_anulada_sin_fecha_o_motivo_rechazada(
    db_session_factory, seed_users, extra
) -> None:
    from app.models import Venta

    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        session.add(
            Venta(
                usuario_id=uid,
                total=100,
                idempotency_key=str(uuid.uuid4()),
                estado="anulada",
                confirmada_at=datetime.now(timezone.utc),
                **extra,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_venta_anulada_completa_persiste(db_session_factory, seed_users) -> None:
    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        ahora = datetime.now(timezone.utc)
        venta = _venta(
            session,
            uid,
            estado="anulada",
            confirmada_at=ahora,
            confirmada_por_id=uid,
            anulada_at=ahora,
            anulada_por_id=uid,
            motivo_anulacion="cliente se arrepintio",
        )
        session.refresh(venta)
        assert venta.motivo_anulacion == "cliente se arrepintio"


def test_idempotency_key_duplicada_mismo_usuario_rechazada(
    db_session_factory, seed_users
) -> None:
    from app.models import Venta

    uid, _, _ = _base(db_session_factory)
    clave = str(uuid.uuid4())
    with db_session_factory() as session:
        _venta(session, uid, idempotency_key=clave)
        session.add(Venta(usuario_id=uid, total=500, idempotency_key=clave))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_idempotency_key_igual_en_usuarios_distintos_permitida(
    db_session_factory, seed_users
) -> None:
    from app.models import Venta

    duena_id, mostrador_id, _ = _base(db_session_factory)
    clave = str(uuid.uuid4())
    with db_session_factory() as session:
        _venta(session, duena_id, idempotency_key=clave)
        _venta(session, mostrador_id, idempotency_key=clave)
        assert session.query(Venta).count() == 2


# --- LineaVenta ---


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("cantidad", 0),
        ("cantidad", -1),
        ("precio_unit", 0),
        ("precio_unit", -5),
        ("subtotal", 0),
        ("subtotal", -5),
    ],
)
def test_linea_valores_no_positivos_rechazados(
    db_session_factory, seed_users, campo, valor
) -> None:
    uid, _, pid = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        session.add(_linea(venta.id, pid, **{campo: valor}))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_linea_valida_persiste(db_session_factory, seed_users) -> None:
    uid, _, pid = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        linea = _linea(venta.id, pid)
        session.add(linea)
        session.commit()
        session.refresh(linea)
        assert linea.id
        assert (linea.cantidad, linea.precio_unit, linea.subtotal) == (2, 1500, 3000)


def test_producto_repetido_en_venta_rechazado(db_session_factory, seed_users) -> None:
    uid, _, pid = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        session.add(_linea(venta.id, pid))
        session.commit()
        session.add(_linea(venta.id, pid, cantidad=1, subtotal=1500))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_mismo_producto_en_ventas_distintas_permitido(
    db_session_factory, seed_users
) -> None:
    from app.models import LineaVenta

    uid, _, pid = _base(db_session_factory)
    with db_session_factory() as session:
        for _ in range(2):
            venta = _venta(session, uid)
            session.add(_linea(venta.id, pid))
        session.commit()
        assert session.query(LineaVenta).count() == 2


def test_linea_update_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import LineaVenta

    uid, _, pid = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        linea = _linea(venta.id, pid)
        session.add(linea)
        session.commit()
        linea_id = linea.id
    with db_session_factory() as session:
        linea = session.get(LineaVenta, linea_id)
        linea.cantidad = 99
        with pytest.raises(InvalidRequestError):
            session.commit()
        session.rollback()
        assert session.get(LineaVenta, linea_id).cantidad == 2


def test_linea_delete_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import LineaVenta

    uid, _, pid = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        linea = _linea(venta.id, pid)
        session.add(linea)
        session.commit()
        linea_id = linea.id
    with db_session_factory() as session:
        session.delete(session.get(LineaVenta, linea_id))
        with pytest.raises(InvalidRequestError):
            session.commit()
        session.rollback()
        assert session.get(LineaVenta, linea_id) is not None


# --- PagoVenta ---


@pytest.mark.parametrize("monto", [0, -100])
def test_pago_monto_no_positivo_rechazado(
    db_session_factory, seed_users, monto
) -> None:
    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        session.add(_pago(venta.id, monto=monto))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_pago_valido_persiste_con_created_at(db_session_factory, seed_users) -> None:
    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        pago = _pago(venta.id, metodo="mp", monto=3000, ref_mp="MP-1")
        session.add(pago)
        session.commit()
        session.refresh(pago)
        assert pago.ref_mp == "MP-1"
        assert pago.created_at is not None


@pytest.mark.parametrize("metodo", ["efectivo", "transferencia", "tarjeta"])
def test_pago_con_ref_mp_en_metodo_distinto_de_mp_rechazado(
    db_session_factory, seed_users, metodo
) -> None:
    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        session.add(_pago(venta.id, metodo=metodo, ref_mp="MP-X"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_pagos_sin_ref_mp_pueden_repetirse(db_session_factory, seed_users) -> None:
    from app.models import PagoVenta

    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        session.add_all([_pago(venta.id, monto=1000), _pago(venta.id, monto=2000)])
        session.commit()
        assert session.query(PagoVenta).count() == 2


def test_ref_mp_duplicado_entre_pagos_rechazado(db_session_factory, seed_users) -> None:
    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta_a = _venta(session, uid)
        venta_b = _venta(session, uid)
        session.add(_pago(venta_a.id, metodo="mp", ref_mp="MP-123"))
        session.commit()
        session.add(_pago(venta_b.id, metodo="mp", ref_mp="MP-123"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_pago_update_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import PagoVenta

    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        pago = _pago(venta.id)
        session.add(pago)
        session.commit()
        pago_id = pago.id
    with db_session_factory() as session:
        pago = session.get(PagoVenta, pago_id)
        pago.monto = 1
        with pytest.raises(InvalidRequestError):
            session.commit()
        session.rollback()
        assert session.get(PagoVenta, pago_id).monto == 3000


def test_pago_delete_bloqueado(db_session_factory, seed_users) -> None:
    from app.models import PagoVenta

    uid, _, _ = _base(db_session_factory)
    with db_session_factory() as session:
        venta = _venta(session, uid)
        pago = _pago(venta.id)
        session.add(pago)
        session.commit()
        pago_id = pago.id
    with db_session_factory() as session:
        session.delete(session.get(PagoVenta, pago_id))
        with pytest.raises(InvalidRequestError):
            session.commit()
        session.rollback()
        assert session.get(PagoVenta, pago_id) is not None


# --- EventoOutbox ---


def test_evento_outbox_pendiente_por_defecto(db_session_factory, seed_users) -> None:
    from app.models import EventoOutbox

    with db_session_factory() as session:
        evento = EventoOutbox(tipo="venta.confirmada", agregado_id="v-1")
        session.add(evento)
        session.commit()
        session.refresh(evento)
        assert evento.id
        assert evento.procesado_at is None
        assert evento.created_at is not None


def test_evento_outbox_duplicado_tipo_agregado_rechazado(
    db_session_factory, seed_users
) -> None:
    from app.models import EventoOutbox

    with db_session_factory() as session:
        session.add(EventoOutbox(tipo="venta.confirmada", agregado_id="v-1"))
        session.commit()
        session.add(EventoOutbox(tipo="venta.confirmada", agregado_id="v-1"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_evento_outbox_mismo_agregado_con_otro_tipo_permitido(
    db_session_factory, seed_users
) -> None:
    from app.models import EventoOutbox

    with db_session_factory() as session:
        session.add(EventoOutbox(tipo="venta.confirmada", agregado_id="v-1"))
        session.add(EventoOutbox(tipo="venta.anulada", agregado_id="v-1"))
        session.commit()
        assert session.query(EventoOutbox).count() == 2


def test_tipo_movimiento_no_cambia_con_ventas() -> None:
    """D3: la anulacion reutiliza `venta`; el enum de movimientos no se toca."""
    from app.models import TIPO_MOVIMIENTO

    assert TIPO_MOVIMIENTO == ("venta", "entrada", "ajuste", "apertura")
