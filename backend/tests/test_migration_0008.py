"""Migracion 0008 (costo congelado y indice de reportes) ejecutada de verdad (C-14 task 3.3).

0002 usa CREATE EXTENSION (solo Postgres), asi que la cadena completa no corre
en SQLite. Se arma el esquema previo con metadata sin las tablas de ventas, se
sella en 0006 y se aplica la 0007 REAL (queda el esquema de ventas sin
`costo_unit` ni el indice de reportes); sobre eso se ejercita 0008: upgrade,
downgrade -1 y re-upgrade. El DDL de Postgres se verifica ademas renderizando
el SQL offline. La verificacion contra Postgres real vive en
test_migration_pg.py (pg_only: necesita TEST_PG_URL).
"""

import io
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
VENTAS_TABLAS = {"venta", "linea_venta", "pago_venta", "evento_outbox"}
INDICE = "ix_venta_estado_confirmada_at"
CHECK = "ck_linea_venta_costo_unit_positivo"


@pytest.fixture()
def alembic_en_0007(tmp_path, monkeypatch):
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
    command.upgrade(cfg, "0007")
    yield cfg, url
    get_settings.cache_clear()


def _sembrar_linea_previa(url: str) -> None:
    """Una venta con una linea tal como la dejaba C-10 (sin costo_unit)."""
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO usuarios (id, email, password_hash, rol) "
                    "VALUES ('u1', 'u@test.only', 'x', 'duena')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO productos (id, sku, nombre, unidad, costo, "
                    "margen_pct, stock_actual, stock_minimo) VALUES "
                    "('p1', 'SKU-M8', 'Alimento', 'bolsa', 100, 0.5, 5, 0)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO venta (id, usuario_id, total, idempotency_key) "
                    "VALUES ('v1', 'u1', 300, 'k1')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO linea_venta (id, venta_id, producto_id, cantidad, "
                    "precio_unit, subtotal) VALUES ('l1', 'v1', 'p1', 2, 150, 300)"
                )
            )
    finally:
        engine.dispose()


def _columnas(url: str, tabla: str) -> dict:
    engine = create_engine(url)
    try:
        return {c["name"]: c for c in inspect(engine).get_columns(tabla)}
    finally:
        engine.dispose()


def _indices(url: str, tabla: str) -> dict:
    engine = create_engine(url)
    try:
        return {i["name"]: i for i in inspect(engine).get_indexes(tabla)}
    finally:
        engine.dispose()


def _checks(url: str, tabla: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {c["name"] for c in inspect(engine).get_check_constraints(tabla)}
    finally:
        engine.dispose()


def test_0008_es_hija_de_0007_y_cabeza() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0008"]
    assert script.get_revision("0008").down_revision == "0007"


def test_0008_agrega_columna_nullable_check_e_indice(alembic_en_0007) -> None:
    from alembic import command

    cfg, url = alembic_en_0007
    assert "costo_unit" not in _columnas(url, "linea_venta")
    assert INDICE not in _indices(url, "venta")
    command.upgrade(cfg, "0008")
    columna = _columnas(url, "linea_venta")["costo_unit"]
    assert columna["nullable"] is True
    assert CHECK in _checks(url, "linea_venta")
    assert _indices(url, "venta")[INDICE]["column_names"] == ["estado", "confirmada_at"]


def test_0008_lineas_previas_quedan_con_costo_nulo_y_el_resto_intacto(
    alembic_en_0007,
) -> None:
    from alembic import command

    cfg, url = alembic_en_0007
    _sembrar_linea_previa(url)
    command.upgrade(cfg, "0008")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            fila = conn.execute(
                text(
                    "SELECT id, venta_id, producto_id, cantidad, precio_unit, "
                    "subtotal, costo_unit FROM linea_venta"
                )
            ).one()
    finally:
        engine.dispose()
    assert tuple(fila[:3]) == ("l1", "v1", "p1")
    assert (fila[3], float(fila[4]), float(fila[5])) == (2, 150.0, 300.0)
    assert fila[6] is None


def _insertar_linea(url: str, costo_sql: str, linea_id: str = "l2") -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO linea_venta (id, venta_id, producto_id, cantidad, "
                    f"precio_unit, subtotal, costo_unit) VALUES ('{linea_id}', 'v1', "
                    f"'p1', 1, 10, 10, {costo_sql})"
                )
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("costo", ["0", "-5"])
def test_0008_base_rechaza_costo_no_positivo(alembic_en_0007, costo) -> None:
    from alembic import command

    cfg, url = alembic_en_0007
    # El producto/venta de la linea previa dan las FKs; se borra la linea previa
    # para que (venta, producto) quede libre para el INSERT bajo prueba.
    _sembrar_linea_previa(url)
    command.upgrade(cfg, "0008")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM linea_venta"))
    finally:
        engine.dispose()
    with pytest.raises(IntegrityError) as exc:
        _insertar_linea(url, costo)
    assert CHECK in str(exc.value)


def test_0008_base_acepta_costo_nulo_o_positivo(alembic_en_0007) -> None:
    from alembic import command

    cfg, url = alembic_en_0007
    _sembrar_linea_previa(url)
    command.upgrade(cfg, "0008")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM linea_venta"))
    finally:
        engine.dispose()
    _insertar_linea(url, "NULL", "l2")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM linea_venta"))
    finally:
        engine.dispose()
    _insertar_linea(url, "0.01", "l3")


def test_0008_downgrade_sin_residuos_y_reupgrade(alembic_en_0007) -> None:
    from alembic import command

    cfg, url = alembic_en_0007
    _sembrar_linea_previa(url)
    command.upgrade(cfg, "0008")
    command.downgrade(cfg, "-1")
    assert "costo_unit" not in _columnas(url, "linea_venta")
    assert INDICE not in _indices(url, "venta")
    assert CHECK not in _checks(url, "linea_venta")
    # El downgrade no rompe lo de 0007: checks, indice de producto y datos siguen.
    assert "ck_linea_venta_cantidad_positiva" in _checks(url, "linea_venta")
    assert "ix_linea_venta_producto_id" in _indices(url, "linea_venta")
    assert "ix_venta_created_at" in _indices(url, "venta")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT cantidad FROM linea_venta")).scalar_one() == 2
    finally:
        engine.dispose()
    command.upgrade(cfg, "0008")
    assert "costo_unit" in _columnas(url, "linea_venta")
    assert INDICE in _indices(url, "venta")
    assert CHECK in _checks(url, "linea_venta")


def test_0008_sql_offline_de_postgres_renderiza_ddl(monkeypatch) -> None:
    """DDL de Postgres sin servidor: ALTER de la columna, check, indice y reverso."""
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/offline")
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.output_buffer = io.StringIO()
        command.upgrade(cfg, "0007:0008", sql=True)
        up = cfg.output_buffer.getvalue()
        cfg.output_buffer = io.StringIO()
        command.downgrade(cfg, "0008:0007", sql=True)
        down = cfg.output_buffer.getvalue()
    finally:
        get_settings.cache_clear()
    assert "ALTER TABLE linea_venta ADD COLUMN costo_unit NUMERIC(10, 2)" in up
    assert (
        f"ALTER TABLE linea_venta ADD CONSTRAINT {CHECK} "
        "CHECK (costo_unit IS NULL OR costo_unit > 0)" in up
    )
    assert f"CREATE INDEX {INDICE} ON venta (estado, confirmada_at)" in up
    assert "NOT NULL" not in up.split("costo_unit NUMERIC(10, 2)")[1].split(";")[0]
    assert f"DROP INDEX {INDICE}" in down
    assert f"ALTER TABLE linea_venta DROP CONSTRAINT {CHECK}" in down
    assert "ALTER TABLE linea_venta DROP COLUMN costo_unit" in down
