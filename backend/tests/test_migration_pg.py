"""Migration 0002 verification against real Postgres (C-02 task 2.2, pg_only).

Skips when no Postgres is reachable (host SQLite/CI runs). Executes inside
the compose network (or any env with TEST_PG_URL / postgresql DATABASE_URL).
Uses a scratch database so the shared `petshop` db is never touched.
"""

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRATCH_DB = "petshop_migtest"


def _base_pg_url() -> str | None:
    url = os.environ.get("TEST_PG_URL")
    if not url:
        try:
            from app.core.config import get_settings

            url = get_settings().database_url
        except Exception:
            return None
    if url is None or not url.startswith("postgresql"):
        return None
    return url


def _can_connect(url: str) -> bool:
    # Broad catch on purpose: unreachable hosts, wrong passwords and even
    # undecodable server messages (psycopg2 vs latin-1 locales) all mean
    # "no usable Postgres here" -> the pg_only tests skip.
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect():
            pass
        engine.dispose()
        return True
    except Exception:
        return False


BASE_PG_URL = _base_pg_url()
needs_pg = pytest.mark.skipif(
    BASE_PG_URL is None or not _can_connect(BASE_PG_URL),
    reason="pg_only: no reachable Postgres (set TEST_PG_URL)",
)


def _scratch_url(base: str) -> str:
    prefix, _, _ = base.rpartition("/")
    return f"{prefix}/{SCRATCH_DB}"


@pytest.fixture()
def migrated_db():
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    base = _base_pg_url()
    assert base is not None
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
        conn.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))
    admin.dispose()

    scratch = _scratch_url(base)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = scratch
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        command.stamp(cfg, "0001")
        command.upgrade(cfg, "head")
        yield scratch
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()
        admin = create_engine(base, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
        admin.dispose()


@needs_pg
def test_migracion_0002_crea_las_4_tablas(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert {"usuarios", "productos", "distribuidoras", "clientes"} <= tables


@needs_pg
def test_migracion_rechaza_stock_negativo_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO productos (id, sku, nombre, unidad, costo, "
                        "margen_pct, stock_actual, stock_minimo) VALUES "
                        "(:id, :sku, :nombre, 'bolsa', 100, 0.5, -1, 0)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "sku": "SKU-PG-NEG",
                        "nombre": "Alimento",
                    },
                )
    finally:
        engine.dispose()


@needs_pg
def test_indice_trgm_sobre_nombre_existe(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE tablename = "
                    "'productos' AND indexname = 'ix_productos_nombre_trgm'"
                )
            ).one_or_none()
    finally:
        engine.dispose()
    assert row is not None
