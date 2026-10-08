"""Importacion de catalogo contra Postgres real (C-08 task 10.2, pg_only).

SQLite no toma `FOR UPDATE` en `aplicar_movimiento`: aca se confirma la
planilla limpia de ejemplo contra una base migrada con Alembic y se
re-confirma para verificar la idempotencia. Skip sin Postgres alcanzable
(TEST_PG_URL), mismo mecanismo que test_migration_pg.py.
"""

import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from tests.test_migration_pg import migrated_db, needs_pg  # noqa: F401


@pytest.fixture()
def pg_session(migrated_db):  # noqa: F811
    engine = create_engine(migrated_db)
    try:
        with sessionmaker(bind=engine, autoflush=False, future=True)() as session:
            yield session
    finally:
        engine.dispose()


@needs_pg
def test_confirmar_la_limpia_y_reconfirmar_es_idempotente(pg_session, tmp_path):
    from app.models import Distribuidora, MovimientoStock, Producto, Usuario
    from app.services.migracion import importar
    from scripts.generar_excel_prueba import generar

    limpia, _ = generar(tmp_path)
    duena = Usuario(email=f"{uuid.uuid4()}@test.only", password_hash="x", rol="duena")
    pg_session.add(duena)
    pg_session.commit()
    contenido = limpia.read_bytes()

    def cuenta(modelo):
        return pg_session.scalar(select(func.count()).select_from(modelo))

    primera = importar(pg_session, contenido, limpia.name, duena, confirmar=True)
    assert primera.confirmado is True and primera.totales.crear == 18
    assert (cuenta(Producto), cuenta(MovimientoStock), cuenta(Distribuidora)) == (18, 17, 3)
    stock = pg_session.scalar(select(func.sum(Producto.stock_actual)))
    aperturas = pg_session.scalar(select(func.sum(MovimientoStock.cantidad)))
    assert stock == aperturas == primera.totales.unidades_apertura
    assert {m.ref_id for m in pg_session.scalars(select(MovimientoStock))} == {primera.lote_id}

    segunda = importar(pg_session, contenido, limpia.name, duena, confirmar=True)
    assert segunda.confirmado is True and segunda.totales.sin_cambios == 18
    assert (cuenta(Producto), cuenta(MovimientoStock), cuenta(Distribuidora)) == (18, 17, 3)
