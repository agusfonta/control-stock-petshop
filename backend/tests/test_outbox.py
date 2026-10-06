"""Outbox transaccional (C-10 task 4.1, RED-first, D11).

registrar_evento hace add + flush SIN commit: el evento vive o muere con la
transaccion del llamador. Un evento por (tipo, agregado_id); solo los tipos
de venta; pendientes() devuelve los no procesados en orden de creacion. En
RED fallan: el modulo app.services.outbox no existe.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError


def _contar(db_session_factory) -> int:
    from app.models import EventoOutbox

    with db_session_factory() as session:
        return session.query(EventoOutbox).count()


def test_registrar_evento_no_hace_commit(db_session_factory) -> None:
    from app.services.outbox import registrar_evento

    with db_session_factory() as session:
        evento = registrar_evento(session, "venta.confirmada", "v-1")
        assert evento.id is not None  # flush: ya tiene id y esta en la sesion
        session.rollback()
    assert _contar(db_session_factory) == 0


def test_commit_del_llamador_persiste_el_evento_pendiente(db_session_factory) -> None:
    from app.models import EventoOutbox
    from app.services.outbox import registrar_evento

    with db_session_factory() as session:
        registrar_evento(session, "venta.confirmada", "v-1")
        session.commit()
    with db_session_factory() as session:
        (evento,) = session.query(EventoOutbox).all()
        assert (evento.tipo, evento.agregado_id) == ("venta.confirmada", "v-1")
        assert evento.procesado_at is None
        assert evento.created_at is not None


def test_mismo_tipo_y_agregado_levanta_integrity_error_al_flush(
    db_session_factory,
) -> None:
    from app.services.outbox import registrar_evento

    with db_session_factory() as session:
        registrar_evento(session, "venta.anulada", "v-1")
        session.commit()
        with pytest.raises(IntegrityError):
            registrar_evento(session, "venta.anulada", "v-1")
        session.rollback()
    assert _contar(db_session_factory) == 1


def test_mismo_agregado_con_otro_tipo_se_registra(db_session_factory) -> None:
    from app.services.outbox import registrar_evento

    with db_session_factory() as session:
        registrar_evento(session, "venta.confirmada", "v-1")
        registrar_evento(session, "venta.anulada", "v-1")
        session.commit()
    assert _contar(db_session_factory) == 2


@pytest.mark.parametrize("tipo", ["venta.creada", "", "VENTA.CONFIRMADA", "otro"])
def test_tipo_fuera_de_los_de_venta_levanta_value_error(
    db_session_factory, tipo
) -> None:
    from app.services.outbox import registrar_evento

    with db_session_factory() as session:
        with pytest.raises(ValueError):
            registrar_evento(session, tipo, "v-1")
        session.commit()
    assert _contar(db_session_factory) == 0


def test_pendientes_devuelve_solo_sin_procesar_en_orden_de_creacion(
    db_session_factory,
) -> None:
    from app.models import EventoOutbox
    from app.services.outbox import pendientes

    base = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    with db_session_factory() as session:
        session.add_all(
            [
                EventoOutbox(
                    tipo="venta.confirmada",
                    agregado_id="v-tarde",
                    created_at=base + timedelta(minutes=2),
                ),
                EventoOutbox(
                    tipo="venta.confirmada",
                    agregado_id="v-procesado",
                    created_at=base + timedelta(minutes=1),
                    procesado_at=base + timedelta(minutes=5),
                ),
                EventoOutbox(
                    tipo="venta.anulada",
                    agregado_id="v-temprano",
                    created_at=base,
                ),
            ]
        )
        session.commit()
    with db_session_factory() as session:
        assert [e.agregado_id for e in pendientes(session)] == ["v-temprano", "v-tarde"]


def test_pendientes_vacio_sin_eventos(db_session_factory) -> None:
    from app.services.outbox import pendientes

    with db_session_factory() as session:
        assert pendientes(session) == []


def test_pendientes_es_de_solo_lectura(db_session_factory) -> None:
    from app.models import EventoOutbox
    from app.services.outbox import pendientes, registrar_evento

    with db_session_factory() as session:
        registrar_evento(session, "venta.confirmada", "v-1")
        session.commit()
    with db_session_factory() as session:
        pendientes(session)
        pendientes(session)
        assert not session.dirty and not session.new and not session.deleted
        assert session.query(EventoOutbox).filter(
            EventoOutbox.procesado_at.isnot(None)
        ).count() == 0
