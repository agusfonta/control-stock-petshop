"""Migracion 0006 (compras) ejecutada de verdad sin Postgres (C-07 task 2.3).

0002 usa CREATE EXTENSION (solo Postgres), asi que la cadena completa no
corre en SQLite. Se arma el esquema previo con metadata (sin las 4 tablas
nuevas), se sella en 0005 y se ejercita 0006: upgrade, downgrade -1 y
re-upgrade. La verificacion contra Postgres real vive en
test_migration_pg.py (pg_only; CI la ejecuta).
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
COMPRAS_TABLAS = {"pedido_compra", "linea_pedido", "entrada_stock", "pago_distribuidora"}


@pytest.fixture()
def alembic_sqlite(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings
    from app.models import Base

    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    previas = [t for t in Base.metadata.sorted_tables if t.name not in COMPRAS_TABLAS]
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=previas)
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.stamp(cfg, "0005")
    yield cfg, url
    get_settings.cache_clear()


def _tablas(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_0006_upgrade_downgrade_upgrade_sin_residuos(alembic_sqlite) -> None:
    from alembic import command

    cfg, url = alembic_sqlite
    assert not (COMPRAS_TABLAS & _tablas(url))
    command.upgrade(cfg, "head")
    assert COMPRAS_TABLAS <= _tablas(url)
    command.downgrade(cfg, "-1")
    assert not (COMPRAS_TABLAS & _tablas(url))
    command.upgrade(cfg, "head")
    assert COMPRAS_TABLAS <= _tablas(url)


def test_0006_crea_indices_y_uniques(alembic_sqlite) -> None:
    from alembic import command

    cfg, url = alembic_sqlite
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        insp = inspect(engine)
        assert {"ix_pedido_compra_distribuidora_id", "ix_pedido_compra_estado"} <= {
            i["name"] for i in insp.get_indexes("pedido_compra")
        }
        assert "ix_pago_distribuidora_distribuidora_id" in {
            i["name"] for i in insp.get_indexes("pago_distribuidora")
        }
        for tabla in ("linea_pedido", "entrada_stock"):
            columnas = [
                set(u["column_names"]) for u in insp.get_unique_constraints(tabla)
            ]
            assert {"pedido_id", "producto_id"} in columnas
    finally:
        engine.dispose()


def test_0006_base_rechaza_cantidad_cero_y_monto_cero(alembic_sqlite) -> None:
    from alembic import command

    cfg, url = alembic_sqlite
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO linea_pedido (id, pedido_id, producto_id, "
                        "cantidad, costo_unitario) VALUES ('l', 'p', 'x', 0, 100)"
                    )
                )
        with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO pago_distribuidora (id, distribuidora_id, "
                        "monto, metodo, usuario_id) VALUES "
                        "('g', 'd', 0, 'efectivo', 'u')"
                    )
                )
    finally:
        engine.dispose()
