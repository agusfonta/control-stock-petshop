"""Modelo de cliente."""


from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Numeric,
    String,
)

from app.core.base import AuditMixin, _uuid
from app.core.db import Base


class Cliente(Base, AuditMixin):
    """Counter customer, optionally with cuenta-corriente balance."""

    __tablename__ = "clientes"

    id = Column(String(36), primary_key=True, default=_uuid)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    saldo_cc = Column(Numeric(10, 2), nullable=False, default=0, server_default="0")


class Mascota(Base, AuditMixin):
    """Mascota de un cliente (C-17); soft-delete por `activo`."""

    __tablename__ = "mascotas"
    __table_args__ = (
        CheckConstraint("tipo IN ('perro', 'gato', 'otro')", name="ck_mascotas_tipo"),
        Index("ix_mascotas_cliente_id", "cliente_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    cliente_id = Column(String(36), ForeignKey("clientes.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(10), nullable=False)
