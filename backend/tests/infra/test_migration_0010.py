"""Migracion 0010 (tabla mascotas, C-17) ejecutada de verdad sobre SQLite."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.alembic_helpers import limpiar_settings, preparar_alembic, tablas

BACKEND_DIR = Path(__file__).resolve().parents[2]
VENTAS_TABLAS = {"venta", "linea_venta", "pago_venta", "evento_outbox"}


@pytest.fixture()
def alembic_en_0009(tmp_path, monkeypatch):
    # `mascotas` la crea 0010: se excluye del esquema previo.
    yield preparar_alembic(tmp_path, monkeypatch, VENTAS_TABLAS | {"mascotas"}, "0006", "0009")
    limpiar_settings()


def _sql_de(url: str, nombre: str) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT sql FROM sqlite_master WHERE name = :n"), {"n": nombre}
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def test_0010_es_hija_de_0009_y_cabeza() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0010"]
    assert script.get_revision("0010").down_revision == "0009"


def test_0010_upgrade_crea_tabla_indice_y_check(alembic_en_0009) -> None:
    from alembic import command

    cfg, url = alembic_en_0009
    assert "mascotas" not in tablas(url)
    command.upgrade(cfg, "0010")
    assert "mascotas" in tablas(url)
    assert _sql_de(url, "ix_mascotas_cliente_id") is not None
    ddl = _sql_de(url, "mascotas")
    assert "ck_mascotas_tipo" in ddl
    assert "REFERENCES clientes" in ddl


def test_0010_downgrade_elimina_tabla_e_indice_y_reupgrade(alembic_en_0009) -> None:
    from alembic import command

    cfg, url = alembic_en_0009
    command.upgrade(cfg, "0010")
    command.downgrade(cfg, "-1")
    assert "mascotas" not in tablas(url)
    assert _sql_de(url, "ix_mascotas_cliente_id") is None
    assert "clientes" in tablas(url)
    command.upgrade(cfg, "0010")
    assert "mascotas" in tablas(url)
