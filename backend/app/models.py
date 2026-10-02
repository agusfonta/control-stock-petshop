"""ORM models. C-01: only Base re-export (zero tables by design)."""

from app.core.db import Base

__all__ = ["Base"]
