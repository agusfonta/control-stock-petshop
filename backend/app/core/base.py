"""Piezas base compartidas por los modelos ORM."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, func


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
