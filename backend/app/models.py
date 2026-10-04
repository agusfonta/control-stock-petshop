"""Domain ORM models (C-02 core-models).

Single module by design (split only when sales/purchases arrive in C-05).
Money as Numeric; precio_venta is a read-time column_property (RN-PR-01);
roles as native Enum (duena/mostrador). Auth logic belongs to C-03.
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import column_property, relationship

from app.core.db import Base

__all__ = [
    "Base",
    "AuditMixin",
    "Usuario",
    "Producto",
    "ListaPrecio",
    "Distribuidora",
    "Cliente",
    "MovimientoStock",
]

ROL_USUARIO = ("duena", "mostrador")
UNIDAD_PRODUCTO = ("unidad", "bolsa", "caja")
TIPO_MOVIMIENTO = ("venta", "entrada", "ajuste", "apertura")


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditMixin:
    """activo soft-delete flag + server-managed audit timestamps."""

    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Usuario(Base, AuditMixin):
    """App user. Password hashing/verification belongs to C-03 (auth)."""

    __tablename__ = "usuarios"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    rol = Column(Enum(*ROL_USUARIO, name="rol_usuario"), nullable=False)


class Distribuidora(Base, AuditMixin):
    """Supplier/distributor of products."""

    __tablename__ = "distribuidoras"

    id = Column(String(36), primary_key=True, default=_uuid)
    nombre = Column(String, nullable=False)
    contacto = Column(String, nullable=True)
    cuit = Column(String, nullable=True)
    condiciones = Column(String, nullable=True)

class Producto(Base, AuditMixin):
    """Sellable item. precio_venta is always costo*(1+margen) (RN-PR-01)."""

    __tablename__ = "productos"
    __table_args__ = (
        CheckConstraint("stock_actual >= 0", name="ck_productos_stock_no_negativo"),
        # GIN/trgm on Postgres; plain index elsewhere (SQLite ignores
        # postgresql_* kwargs). Mirrors 0002 (raw CREATE INDEX for the opclass).
        Index(
            "ix_productos_nombre_trgm",
            "nombre",
            postgresql_using="gin",
            postgresql_ops={"nombre": "gin_trgm_ops"},
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    sku = Column(String, nullable=False, unique=True)
    nombre = Column(String, nullable=False)
    marca = Column(String, nullable=True)
    categoria = Column(String, nullable=True, index=True)
    unidad = Column(
        Enum(*UNIDAD_PRODUCTO, name="unidad_producto"),
        nullable=False,
        default="unidad",
        server_default="unidad",
    )
    costo = Column(Numeric(10, 2), nullable=False)
    margen_pct = Column(Numeric(5, 4), nullable=False, default=0)
    stock_actual = Column(Integer, nullable=False, default=0, server_default="0")
    stock_minimo = Column(Integer, nullable=False, default=0, server_default="0")
    distribuidora_default_id = Column(
        String(36),
        ForeignKey("distribuidoras.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )


# Read-time price (no physical column, no triggers): RN-PR-01 always current.
# NOTE: transient instances (never flushed) cannot evaluate this expression;
# flush/commit + refresh before reading precio_venta.
Producto.precio_venta = column_property(Producto.costo * (1 + Producto.margen_pct))


class ListaPrecio(Base, AuditMixin):
    """Costo de un producto por distribuidora (RN-PR-03). Persistence only in
    C-04 — the per-distributor price calculation arrives with C-06/C-07."""

    __tablename__ = "lista_precio"
    __table_args__ = (
        # One cost per (distribuidora, producto) pair.
        UniqueConstraint(
            "distribuidora_id",
            "producto_id",
            name="uq_lista_precio_distribuidora_producto",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    distribuidora_id = Column(
        String(36),
        ForeignKey("distribuidoras.id"),
        nullable=False,
    )
    producto_id = Column(
        String(36),
        ForeignKey("productos.id"),
        nullable=False,
    )
    costo = Column(Numeric(10, 2), nullable=False)

    distribuidora = relationship("Distribuidora", backref="lista_precios")
    producto = relationship("Producto", backref="lista_precios")


class Cliente(Base, AuditMixin):
    """Counter customer, optionally with cuenta-corriente balance."""

    __tablename__ = "clientes"

    id = Column(String(36), primary_key=True, default=_uuid)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    saldo_cc = Column(Numeric(10, 2), nullable=False, default=0, server_default="0")


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
