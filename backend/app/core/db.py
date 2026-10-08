"""Database engine/session wiring. No tables in C-01 (Base only)."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models (C-02 adds domain models)."""


def build_engine(url: str) -> Engine:
    """Crea el engine; SQLite (solo dev/test) permite uso entre hilos.

    El servidor de desarrollo atiende cada request en un hilo distinto, por lo
    que SQLite necesita `check_same_thread=False` (C-13 D14).
    """
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(
        url, pool_pre_ping=True, future=True, connect_args=connect_args
    )


_settings = get_settings()
engine = build_engine(_settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
