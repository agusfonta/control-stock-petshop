"""Modelos de distribuidora y lista de precios."""


from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.base import AuditMixin, _uuid
from app.core.db import Base


class Distribuidora(Base, AuditMixin):
    """Supplier/distributor of products."""

    __tablename__ = "distribuidoras"

    id = Column(String(36), primary_key=True, default=_uuid)
    nombre = Column(String, nullable=False)
    contacto = Column(String, nullable=True)
    cuit = Column(String, nullable=True)
    condiciones = Column(String, nullable=True)


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
        Index("ix_lista_precio_producto_id", "producto_id"),
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
