"""Modelo de usuarios (auth)."""


from sqlalchemy import (
    Column,
    Enum,
    String,
)

from app.core.base import AuditMixin, _uuid
from app.core.db import Base

ROL_USUARIO = ("duena", "mostrador")


class Usuario(Base, AuditMixin):
    """App user. Password hashing/verification belongs to C-03 (auth)."""

    __tablename__ = "usuarios"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    rol = Column(Enum(*ROL_USUARIO, name="rol_usuario"), nullable=False)
