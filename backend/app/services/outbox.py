"""Outbox transaccional minimo (C-10, D11).

registrar_evento deja un evento pendiente en la MISMA transaccion que la
transicion de la venta: hace add + flush pero NUNCA commit ni rollback (el
duenio de la transaccion es el llamador), asi el evento persiste si y solo
si la transicion persiste, sin perdidas ni duplicados. El unique
(tipo, agregado_id) impide duplicarlo aunque la operacion se repita. C-10 no
tiene consumidor: C-11 (FE) tomara los pendientes y marcara procesado_at.
"""

from sqlalchemy.orm import Session

from app.models import EventoOutbox

__all__ = ["TIPOS_EVENTO", "registrar_evento", "pendientes"]

TIPOS_EVENTO = ("venta.confirmada", "venta.anulada")


def registrar_evento(db: Session, tipo: str, agregado_id: str) -> EventoOutbox:
    """Agrega un evento pendiente a la transaccion del llamador (sin commit).

    ValueError si `tipo` no es de venta (no se escribe nada). Un segundo
    registro del mismo (tipo, agregado_id) levanta IntegrityError en el
    flush, que el llamador decide como tratar (replay o rollback).
    """
    if tipo not in TIPOS_EVENTO:
        raise ValueError(f"tipo de evento invalido: {tipo!r}")
    evento = EventoOutbox(tipo=tipo, agregado_id=agregado_id)
    db.add(evento)
    db.flush()
    return evento


def pendientes(db: Session) -> list[EventoOutbox]:
    """Eventos sin procesar en orden de creacion (solo lectura)."""
    return (
        db.query(EventoOutbox)
        .filter(EventoOutbox.procesado_at.is_(None))
        .order_by(EventoOutbox.created_at, EventoOutbox.id)
        .all()
    )
