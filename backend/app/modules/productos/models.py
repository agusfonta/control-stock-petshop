"""Modelo de producto (catalogo)."""


from sqlalchemy import (
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import column_property

from app.core.base import AuditMixin, _uuid
from app.core.db import Base

UNIDAD_PRODUCTO = ("unidad", "bolsa", "caja")


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
