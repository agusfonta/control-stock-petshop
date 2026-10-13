"""Libro append-only de movimientos de stock."""


from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
    func,
)
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import relationship

from app.core.base import _uuid
from app.core.db import Base

TIPO_MOVIMIENTO = ("venta", "entrada", "ajuste", "apertura")


class MovimientoStock(Base):
    """Append-only ledger of every stock change (C-05, RN-ST-03).

    One row per mutation with signed cantidad + stock_previo/stock_nuevo.
    No updated_at/activo: rows are never modified. ORM-level UPDATE/DELETE
    are blocked via event listeners (decision D7); the DB check on
    stock_nuevo is the last barrier (defense in depth with Pydantic).
    Stock before C-05 has no rows: it counts as opening balance (no backfill).
    """

    __tablename__ = "movimiento_stock"
    __table_args__ = (
        CheckConstraint(
            "stock_nuevo >= 0", name="ck_movimiento_stock_nuevo_no_negativo"
        ),
        Index("ix_movimiento_stock_producto_id", "producto_id"),
        Index("ix_movimiento_stock_created_at", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    producto_id = Column(
        String(36),
        ForeignKey("productos.id"),
        nullable=False,
    )
    tipo = Column(
        Enum(*TIPO_MOVIMIENTO, name="tipo_movimiento"),
        nullable=False,
    )
    cantidad = Column(Integer, nullable=False)
    stock_previo = Column(Integer, nullable=False)
    stock_nuevo = Column(Integer, nullable=False)
    ref_id = Column(String(36), nullable=True)
    motivo = Column(String, nullable=True)
    usuario_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    producto = relationship("Producto", backref="movimientos")
    usuario = relationship("Usuario", backref="movimientos_stock")


@event.listens_for(MovimientoStock, "before_update")
def _bloquear_update_movimiento(mapper, connection, target) -> None:
    """Reject any UPDATE: the ledger is insert-only (RN-ST-03)."""
    raise InvalidRequestError(
        "movimiento_stock es append-only: update bloqueado"
    )


@event.listens_for(MovimientoStock, "before_delete")
def _bloquear_delete_movimiento(mapper, connection, target) -> None:
    """Reject any DELETE: the ledger is insert-only (RN-ST-03)."""
    raise InvalidRequestError(
        "movimiento_stock es append-only: delete bloqueado"
    )
