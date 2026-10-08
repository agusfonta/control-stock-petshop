"""Migracion 0009 (drop de evento_outbox) ejecutada de verdad.

0002 usa CREATE EXTENSION (solo Postgres), asi que la cadena completa no corre
en SQLite. Se arma el esquema previo con metadata sin las tablas de ventas, se
sella en 0006 y se aplican las migraciones REALES 0007 y 0008 (queda el esquema
con `evento_outbox`); sobre eso se ejercita 0009: upgrade, downgrade -1 y
re-upgrade. El DDL de Postgres se verifica ademas renderizando el SQL offline.
La verificacion contra Postgres real vive en test_migration_pg.py (pg_only).
"""

import io
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
VENTAS_TABLAS = {"venta", "linea_venta", "pago_venta", "evento_outbox"}
TABLA = "evento_outbox"
INDICE = "ix_evento_outbox_pendientes"
UNICA = "uq_evento_outbox_tipo_agregado"


@pytest.fixture()
def alembic_en_0008(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings
    from app.models import Base

    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    previas = [t for t in Base.metadata.sorted_tables if t.name not in VENTAS_TABLAS]
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=previas)
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.stamp(cfg, "0006")
    command.upgrade(cfg, "0008")
    yield cfg, url
    get_settings.cache_clear()


def _tablas(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _sql_de(url: str, nombre: str) -> str | None:
    """DDL almacenado por SQLite para una tabla o indice (None si no existe)."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT sql FROM sqlite_master WHERE name = :n"), {"n": nombre}
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def test_0009_es_hija_de_0008_y_cabeza() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0009"]
    assert script.get_revision("0009").down_revision == "0008"


def test_0009_upgrade_elimina_evento_outbox_y_conserva_ventas(alembic_en_0008) -> None:
    from alembic import command

    cfg, url = alembic_en_0008
    assert TABLA in _tablas(url)
    assert _sql_de(url, INDICE) is not None
    command.upgrade(cfg, "0009")
    tablas = _tablas(url)
    assert TABLA not in tablas
    assert _sql_de(url, INDICE) is None
    assert {"venta", "linea_venta", "pago_venta"} <= tablas


def test_0009_downgrade_recrea_evento_outbox_identica_a_0007(alembic_en_0008) -> None:
    from alembic import command

    cfg, url = alembic_en_0008
    ddl_0007 = _sql_de(url, TABLA)
    indice_0007 = _sql_de(url, INDICE)
    command.upgrade(cfg, "0009")
    command.downgrade(cfg, "-1")
    assert TABLA in _tablas(url)
    assert _sql_de(url, TABLA) == ddl_0007
    assert _sql_de(url, INDICE) == indice_0007
    assert UNICA in ddl_0007
    assert "WHERE procesado_at IS NULL" in indice_0007
    # Y se puede volver a subir sin residuos.
    command.upgrade(cfg, "0009")
    assert TABLA not in _tablas(url)
    assert _sql_de(url, INDICE) is None


def test_0009_sql_offline_de_postgres_renderiza_ddl(monkeypatch) -> None:
    """DDL de Postgres sin servidor: DROP en upgrade, CREATE identico en downgrade."""
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/offline")
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.output_buffer = io.StringIO()
        command.upgrade(cfg, "0008:0009", sql=True)
        up = cfg.output_buffer.getvalue()
        cfg.output_buffer = io.StringIO()
        command.downgrade(cfg, "0009:0008", sql=True)
        down = cfg.output_buffer.getvalue()
    finally:
        get_settings.cache_clear()
    assert f"DROP INDEX {INDICE}" in up
    assert f"DROP TABLE {TABLA}" in up
    assert f"CREATE TABLE {TABLA} " in down
    assert f"CONSTRAINT {UNICA} UNIQUE (tipo, agregado_id)" in down
    assert (
        f"CREATE INDEX {INDICE} ON {TABLA} (created_at) "
        "WHERE procesado_at IS NULL" in down
    )
