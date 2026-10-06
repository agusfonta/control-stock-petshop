"""Migracion 0007 (ventas) ejecutada de verdad sin Postgres (C-10 task 2.3).

0002 usa CREATE EXTENSION (solo Postgres), asi que la cadena completa no
corre en SQLite. Se arma el esquema previo con metadata (sin las 4 tablas
nuevas), se sella en 0006 y se ejercita 0007: upgrade, downgrade -1 y
re-upgrade. El DDL de Postgres se verifica ademas renderizando el SQL
offline (sin servidor). La verificacion contra Postgres real vive en
test_migration_pg.py (pg_only: necesita TEST_PG_URL).
"""

import io
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
VENTAS_TABLAS = {"venta", "linea_venta", "pago_venta", "evento_outbox"}


@pytest.fixture()
def alembic_sqlite(tmp_path, monkeypatch):
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
    yield cfg, url
    get_settings.cache_clear()


def _tablas(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_0007_es_hija_de_0006_y_cabeza() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0007"]
    assert script.get_revision("0007").down_revision == "0006"


def test_0007_upgrade_downgrade_upgrade_sin_residuos(alembic_sqlite) -> None:
    from alembic import command

    cfg, url = alembic_sqlite
    assert not (VENTAS_TABLAS & _tablas(url))
    command.upgrade(cfg, "head")
    assert VENTAS_TABLAS <= _tablas(url)
    command.downgrade(cfg, "-1")
    assert not (VENTAS_TABLAS & _tablas(url))
    command.upgrade(cfg, "head")
    assert VENTAS_TABLAS <= _tablas(url)


def test_0007_crea_indices_y_uniques(alembic_sqlite) -> None:
    from alembic import command

    cfg, url = alembic_sqlite
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        insp = inspect(engine)
        assert {
            "ix_venta_cliente_id_created_at",
            "ix_venta_usuario_id_created_at",
            "ix_venta_created_at",
        } <= {i["name"] for i in insp.get_indexes("venta")}
        assert "ix_linea_venta_producto_id" in {
            i["name"] for i in insp.get_indexes("linea_venta")
        }
        assert "ix_pago_venta_venta_id" in {
            i["name"] for i in insp.get_indexes("pago_venta")
        }
        assert "ix_evento_outbox_pendientes" in {
            i["name"] for i in insp.get_indexes("evento_outbox")
        }
        assert {"usuario_id", "idempotency_key"} in [
            set(u["column_names"]) for u in insp.get_unique_constraints("venta")
        ]
        assert {"venta_id", "producto_id"} in [
            set(u["column_names"]) for u in insp.get_unique_constraints("linea_venta")
        ]
        assert {"ref_mp"} in [
            set(u["column_names"]) for u in insp.get_unique_constraints("pago_venta")
        ]
        assert {"tipo", "agregado_id"} in [
            set(u["column_names"])
            for u in insp.get_unique_constraints("evento_outbox")
        ]
    finally:
        engine.dispose()


def _rechaza(engine, sql: str, restriccion: str) -> None:
    """La base rechaza el INSERT por la restriccion indicada (no por otra)."""
    with engine.begin() as conn:
        with pytest.raises(IntegrityError) as exc:
            conn.execute(text(sql))
    assert restriccion in str(exc.value)


def test_0007_base_rechaza_datos_invalidos(alembic_sqlite) -> None:
    from alembic import command

    cfg, url = alembic_sqlite
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        _rechaza(
            engine,
            "INSERT INTO linea_venta (id, venta_id, producto_id, cantidad, "
            "precio_unit, subtotal) VALUES ('l', 'v', 'p', 0, 10, 10)",
            "ck_linea_venta_cantidad_positiva",
        )
        _rechaza(
            engine,
            "INSERT INTO pago_venta (id, venta_id, metodo, monto) "
            "VALUES ('g', 'v', 'efectivo', 0)",
            "ck_pago_venta_monto_positivo",
        )
        _rechaza(
            engine,
            "INSERT INTO pago_venta (id, venta_id, metodo, monto, ref_mp) "
            "VALUES ('g', 'v', 'efectivo', 10, 'MP-1')",
            "ck_pago_venta_ref_mp_solo_mp",
        )
        _rechaza(
            engine,
            "INSERT INTO venta (id, usuario_id, estado, total, idempotency_key) "
            "VALUES ('v', 'u', 'confirmada', 10, 'k')",
            "ck_venta_confirmada_con_fecha",
        )
    finally:
        engine.dispose()


def test_0007_sql_offline_de_postgres_renderiza_ddl(monkeypatch) -> None:
    """DDL de Postgres sin servidor: tablas, enums, indice parcial y downgrade."""
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/offline")
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.output_buffer = io.StringIO()
        command.upgrade(cfg, "0006:0007", sql=True)
        up = cfg.output_buffer.getvalue()
        cfg.output_buffer = io.StringIO()
        command.downgrade(cfg, "0007:0006", sql=True)
        down = cfg.output_buffer.getvalue()
    finally:
        get_settings.cache_clear()
    for tabla in VENTAS_TABLAS:
        assert f"CREATE TABLE {tabla} " in up
        assert f"DROP TABLE {tabla}" in down
    assert "CREATE TYPE estado_venta AS ENUM" in up
    assert "CREATE TYPE metodo_pago_venta AS ENUM" in up
    assert (
        "CREATE INDEX ix_evento_outbox_pendientes ON evento_outbox (created_at) "
        "WHERE procesado_at IS NULL" in up
    )
    assert "DROP TYPE estado_venta" in down
    assert "DROP TYPE metodo_pago_venta" in down
    # D3: la migracion no altera el enum de movimientos.
    assert "tipo_movimiento" not in up
