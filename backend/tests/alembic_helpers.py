"""Helpers comunes de los tests de migraciones sobre SQLite (0006..0009).

0002 usa CREATE EXTENSION (solo Postgres), asi que la cadena completa no corre
en SQLite: se arma el esquema previo con metadata (sin las tablas que crean las
migraciones bajo prueba), se sella en una revision y se aplican las reales.
"""

from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]


def preparar_alembic(
    tmp_path, monkeypatch, excluir: set[str], sellar: str, subir_a: str | None = None
):
    """Arma una base SQLite previa, la sella en `sellar` y devuelve (cfg, url).

    `excluir` son las tablas que NO deben existir antes (las crean las
    migraciones); `subir_a` aplica las migraciones reales hasta esa revision.
    El llamador debe limpiar `get_settings` al terminar (ver `limpiar_settings`).
    """
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings
    from app.models import Base

    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    previas = [t for t in Base.metadata.sorted_tables if t.name not in excluir]
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=previas)
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.stamp(cfg, sellar)
    if subir_a is not None:
        command.upgrade(cfg, subir_a)
    return cfg, url


def limpiar_settings() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()


def tablas(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
