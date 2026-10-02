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
    func,
)
from sqlalchemy.orm import column_property

from app.core.db import Base

__all__ = [
    "Base",
    "AuditMixin",
    "Usuario",
    "Producto",
    "Distribuidora",
    "Cliente",
]

ROL_USUARIO = ("duena", "mostrador")
UNIDAD_PRODUCTO = ("unidad", "bolsa", "caja")


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


class Cliente(Base, AuditMixin):
    """Counter customer, optionally with cuenta-corriente balance."""

    __tablename__ = "clientes"

    id = Column(String(36), primary_key=True, default=_uuid)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    saldo_cc = Column(Numeric(10, 2), nullable=False, default=0, server_default="0")
