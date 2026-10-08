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


@needs_pg
def test_migracion_0003_crea_lista_precio(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert "lista_precio" in tables


@needs_pg
def test_migracion_0004_crea_movimiento_stock(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        tables = set(inspect(engine).get_table_names())
        indexes = inspect(engine).get_indexes("movimiento_stock")
        checks = inspect(engine).get_check_constraints("movimiento_stock")
    finally:
        engine.dispose()
    assert "movimiento_stock" in tables
    assert {"ix_movimiento_stock_producto_id", "ix_movimiento_stock_created_at"} <= {
        i["name"] for i in indexes
    }
    assert "ck_movimiento_stock_nuevo_no_negativo" in {c["name"] for c in checks}


@needs_pg
def test_movimiento_stock_nuevo_negativo_rechazado_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO productos (id, sku, nombre, unidad, costo, "
                    "margen_pct, stock_actual, stock_minimo) VALUES "
                    "('p-mov', 'SKU-PG-MOV', 'Alimento', 'bolsa', 100, 0.5, 10, 2)"
                )
            )
            uid = conn.execute(
                text(
                    "INSERT INTO usuarios (id, email, password_hash, rol) VALUES "
                    "(:id, 'mov@test.only', 'x', 'duena') RETURNING id"
                ),
                {"id": str(uuid.uuid4())},
            ).scalar_one()
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO movimiento_stock (id, producto_id, tipo, "
                        "cantidad, stock_previo, stock_nuevo, usuario_id) VALUES "
                        "(:id, 'p-mov', 'ajuste', -99, 10, -1, :uid)"
                    ),
                    {"id": str(uuid.uuid4()), "uid": uid},
                )
    finally:
        engine.dispose()


@needs_pg
def test_lista_precio_par_distribuidora_producto_unico(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO distribuidoras (id, nombre) VALUES "
                    "('d1', 'Distri')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO productos (id, sku, nombre, unidad, costo, "
                    "margen_pct, stock_actual, stock_minimo) VALUES "
                    "('p1', 'SKU-PG-LP', 'Alimento', 'bolsa', 100, 0.5, 0, 0)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO lista_precio (id, distribuidora_id, producto_id, "
                    "costo) VALUES ('lp1', 'd1', 'p1', 800)"
                )
            )
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO lista_precio (id, distribuidora_id, "
                        "producto_id, costo) VALUES ('lp2', 'd1', 'p1', 900)"
                    )
                )
    finally:
        engine.dispose()


COMPRAS_TABLAS = {"pedido_compra", "linea_pedido", "entrada_stock", "pago_distribuidora"}


@needs_pg
def test_migracion_0006_crea_las_4_tablas_de_compras(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        idx_pedido = {i["name"] for i in insp.get_indexes("pedido_compra")}
        idx_pago = {i["name"] for i in insp.get_indexes("pago_distribuidora")}
    finally:
        engine.dispose()
    assert COMPRAS_TABLAS <= tables
    assert {"ix_pedido_compra_distribuidora_id", "ix_pedido_compra_estado"} <= idx_pedido
    assert "ix_pago_distribuidora_distribuidora_id" in idx_pago


@needs_pg
def test_linea_pedido_cantidad_cero_rechazada_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO distribuidoras (id, nombre) VALUES ('d-c', 'Distri')")
            )
            conn.execute(
                text(
                    "INSERT INTO productos (id, sku, nombre, unidad, costo, "
                    "margen_pct, stock_actual, stock_minimo) VALUES "
                    "('p-c', 'SKU-PG-CMP', 'Alimento', 'bolsa', 100, 0.5, 0, 0)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO usuarios (id, email, password_hash, rol) VALUES "
                    "('u-c', 'cmp@test.only', 'x', 'duena')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO pedido_compra (id, distribuidora_id, usuario_id) "
                    "VALUES ('ped-c', 'd-c', 'u-c')"
                )
            )
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO linea_pedido (id, pedido_id, producto_id, "
                        "cantidad, costo_unitario) VALUES "
                        "('l-c', 'ped-c', 'p-c', 0, 100)"
                    )
                )
    finally:
        engine.dispose()


@needs_pg
def test_downgrade_0006_sin_residuos_y_reupgrade(migrated_db) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # C-14: head es 0008; se baja hasta 0005 (revierte 0008, 0007 y 0006).
    command.downgrade(cfg, "0005")
    engine = create_engine(migrated_db)
    try:
        assert not (COMPRAS_TABLAS & set(inspect(engine).get_table_names()))
        with engine.connect() as conn:
            tipos = {
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT typname FROM pg_type WHERE typname IN "
                        "('estado_pedido', 'metodo_pago_distribuidora')"
                    )
                )
            }
        assert tipos == set()
    finally:
        engine.dispose()
    command.upgrade(cfg, "head")
    engine = create_engine(migrated_db)
    try:
        assert COMPRAS_TABLAS <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


VENTAS_TABLAS = {"venta", "linea_venta", "pago_venta", "evento_outbox"}
VENTAS_TIPOS = {"estado_venta", "metodo_pago_venta"}


def _seed_venta(conn, sufijo: str, usuario_id: str | None = None) -> tuple[str, str]:
    """Inserta usuario (si no se pasa), producto y venta borrador; devuelve ids."""
    if usuario_id is None:
        usuario_id = f"u-{sufijo}"
        conn.execute(
            text(
                "INSERT INTO usuarios (id, email, password_hash, rol) VALUES "
                "(:id, :email, 'x', 'duena')"
            ),
            {"id": usuario_id, "email": f"{sufijo}@test.only"},
        )
    conn.execute(
        text(
            "INSERT INTO productos (id, sku, nombre, unidad, costo, margen_pct, "
            "stock_actual, stock_minimo) VALUES "
            "(:id, :sku, 'Alimento', 'bolsa', 100, 0.5, 5, 0)"
        ),
        {"id": f"p-{sufijo}", "sku": f"SKU-PG-{sufijo}"},
    )
    conn.execute(
        text(
            "INSERT INTO venta (id, usuario_id, total, idempotency_key) VALUES "
            "(:id, :uid, 100, :clave)"
        ),
        {"id": f"v-{sufijo}", "uid": usuario_id, "clave": f"k-{sufijo}"},
    )
    return usuario_id, f"v-{sufijo}"


@needs_pg
def test_migracion_0007_crea_las_4_tablas_de_ventas(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        idx_venta = {i["name"] for i in insp.get_indexes("venta")}
        with engine.connect() as conn:
            tipos = {
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT typname FROM pg_type WHERE typname IN "
                        "('estado_venta', 'metodo_pago_venta', 'tipo_movimiento')"
                    )
                )
            }
            enum_movimiento = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t "
                        "ON e.enumtypid = t.oid WHERE t.typname = 'tipo_movimiento' "
                        "ORDER BY e.enumsortorder"
                    )
                )
            ]
            parcial = conn.execute(
                text(
                    "SELECT indexdef FROM pg_indexes WHERE tablename = "
                    "'evento_outbox' AND indexname = 'ix_evento_outbox_pendientes'"
                )
            ).scalar_one()
    finally:
        engine.dispose()
    assert VENTAS_TABLAS <= tables
    assert {
        "ix_venta_cliente_id_created_at",
        "ix_venta_usuario_id_created_at",
        "ix_venta_created_at",
    } <= idx_venta
    assert VENTAS_TIPOS <= tipos
    assert "WHERE (procesado_at IS NULL)" in parcial
    # D3: el enum de movimientos no cambia con 0007.
    assert enum_movimiento == ["venta", "entrada", "ajuste", "apertura"]


@needs_pg
def test_linea_venta_cantidad_cero_rechazada_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            _, venta_id = _seed_venta(conn, "lv")
            with pytest.raises(IntegrityError) as exc:
                conn.execute(
                    text(
                        "INSERT INTO linea_venta (id, venta_id, producto_id, "
                        "cantidad, precio_unit, subtotal) VALUES "
                        "('l-lv', :v, 'p-lv', 0, 10, 10)"
                    ),
                    {"v": venta_id},
                )
        assert "ck_linea_venta_cantidad_positiva" in str(exc.value)
    finally:
        engine.dispose()


@needs_pg
def test_pago_venta_monto_cero_y_ref_mp_en_efectivo_rechazados_en_pg(
    migrated_db,
) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            _, venta_id = _seed_venta(conn, "pv")
        with engine.begin() as conn:
            with pytest.raises(IntegrityError) as exc:
                conn.execute(
                    text(
                        "INSERT INTO pago_venta (id, venta_id, metodo, monto) "
                        "VALUES ('g1', :v, 'efectivo', 0)"
                    ),
                    {"v": venta_id},
                )
        assert "ck_pago_venta_monto_positivo" in str(exc.value)
        with engine.begin() as conn:
            with pytest.raises(IntegrityError) as exc:
                conn.execute(
                    text(
                        "INSERT INTO pago_venta (id, venta_id, metodo, monto, "
                        "ref_mp) VALUES ('g2', :v, 'efectivo', 10, 'MP-1')"
                    ),
                    {"v": venta_id},
                )
        assert "ck_pago_venta_ref_mp_solo_mp" in str(exc.value)
    finally:
        engine.dispose()


@needs_pg
def test_ref_mp_unico_y_nulls_multiples_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            _, venta_id = _seed_venta(conn, "rm")
            conn.execute(
                text(
                    "INSERT INTO pago_venta (id, venta_id, metodo, monto, ref_mp) "
                    "VALUES ('g1', :v, 'mp', 10, 'MP-9')"
                ),
                {"v": venta_id},
            )
            # NULLs multiples permitidos: pagos sin referencia no colisionan.
            for pid in ("g2", "g3"):
                conn.execute(
                    text(
                        "INSERT INTO pago_venta (id, venta_id, metodo, monto) "
                        "VALUES (:id, :v, 'efectivo', 10)"
                    ),
                    {"id": pid, "v": venta_id},
                )
        with engine.begin() as conn:
            with pytest.raises(IntegrityError) as exc:
                conn.execute(
                    text(
                        "INSERT INTO pago_venta (id, venta_id, metodo, monto, "
                        "ref_mp) VALUES ('g4', :v, 'mp', 10, 'MP-9')"
                    ),
                    {"v": venta_id},
                )
        assert "uq_pago_venta_ref_mp" in str(exc.value)
    finally:
        engine.dispose()


@needs_pg
def test_idempotency_key_unica_por_vendedor_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            uid, _ = _seed_venta(conn, "ik")
            conn.execute(
                text(
                    "INSERT INTO usuarios (id, email, password_hash, rol) VALUES "
                    "('u-otro', 'otro@test.only', 'x', 'mostrador')"
                )
            )
            # Misma clave, otro vendedor: permitida.
            conn.execute(
                text(
                    "INSERT INTO venta (id, usuario_id, total, idempotency_key) "
                    "VALUES ('v-otro', 'u-otro', 50, 'k-ik')"
                )
            )
        with engine.begin() as conn:
            with pytest.raises(IntegrityError) as exc:
                conn.execute(
                    text(
                        "INSERT INTO venta (id, usuario_id, total, "
                        "idempotency_key) VALUES ('v-dup', :u, 50, 'k-ik')"
                    ),
                    {"u": uid},
                )
        assert "uq_venta_usuario_idempotency_key" in str(exc.value)
    finally:
        engine.dispose()


@needs_pg
def test_evento_outbox_unico_por_tipo_y_agregado_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO evento_outbox (id, tipo, agregado_id) VALUES "
                    "('e1', 'venta.confirmada', 'v-1')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO evento_outbox (id, tipo, agregado_id) VALUES "
                    "('e2', 'venta.anulada', 'v-1')"
                )
            )
        with engine.begin() as conn:
            with pytest.raises(IntegrityError) as exc:
                conn.execute(
                    text(
                        "INSERT INTO evento_outbox (id, tipo, agregado_id) VALUES "
                        "('e3', 'venta.confirmada', 'v-1')"
                    )
                )
        assert "uq_evento_outbox_tipo_agregado" in str(exc.value)
    finally:
        engine.dispose()


@needs_pg
def test_downgrade_0007_sin_residuos_y_reupgrade(migrated_db) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # C-14: head es 0008; se baja hasta 0006 (revierte 0008 y 0007).
    command.downgrade(cfg, "0006")
    engine = create_engine(migrated_db)
    try:
        assert not (VENTAS_TABLAS & set(inspect(engine).get_table_names()))
        # 0006 sigue intacta: solo se revirtio 0007 (y 0008 antes).
        assert COMPRAS_TABLAS <= set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            tipos = {
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT typname FROM pg_type WHERE typname IN "
                        "('estado_venta', 'metodo_pago_venta')"
                    )
                )
            }
        assert tipos == set()
    finally:
        engine.dispose()
    command.upgrade(cfg, "head")
    engine = create_engine(migrated_db)
    try:
        assert VENTAS_TABLAS <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _seed_linea_previa(conn, sufijo: str) -> tuple[str, str]:
    """Venta + producto + una linea sin costo_unit; devuelve (venta_id, producto_id)."""
    _, venta_id = _seed_venta(conn, sufijo)
    conn.execute(
        text(
            "INSERT INTO linea_venta (id, venta_id, producto_id, cantidad, "
            "precio_unit, subtotal) VALUES (:l, :v, :p, 2, 150, 300)"
        ),
        {"l": f"l-{sufijo}", "v": venta_id, "p": f"p-{sufijo}"},
    )
    return venta_id, f"p-{sufijo}"


@needs_pg
def test_migracion_0008_agrega_costo_unit_check_e_indice_en_pg(migrated_db) -> None:
    engine = create_engine(migrated_db)
    try:
        insp = inspect(engine)
        columnas = {c["name"]: c for c in insp.get_columns("linea_venta")}
        assert columnas["costo_unit"]["nullable"] is True
        assert "ck_linea_venta_costo_unit_positivo" in {
            c["name"] for c in insp.get_check_constraints("linea_venta")
        }
        indices = {i["name"]: i for i in insp.get_indexes("venta")}
        assert indices["ix_venta_estado_confirmada_at"]["column_names"] == [
            "estado",
            "confirmada_at",
        ]
        with engine.begin() as conn:
            venta_id, producto_id = _seed_linea_previa(conn, "c8")
            # NULL aceptado (linea previa) y positivo aceptado.
            assert (
                conn.execute(
                    text("SELECT costo_unit FROM linea_venta WHERE id = 'l-c8'")
                ).scalar_one()
                is None
            )
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM linea_venta"))
            conn.execute(
                text(
                    "INSERT INTO linea_venta (id, venta_id, producto_id, cantidad, "
                    "precio_unit, subtotal, costo_unit) VALUES "
                    "('l-ok', :v, :p, 1, 10, 10, 0.01)"
                ),
                {"v": venta_id, "p": producto_id},
            )
        for costo in ("0", "-5"):
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM linea_venta"))
                with pytest.raises(IntegrityError) as exc:
                    conn.execute(
                        text(
                            "INSERT INTO linea_venta (id, venta_id, producto_id, "
                            "cantidad, precio_unit, subtotal, costo_unit) VALUES "
                            f"('l-bad', :v, :p, 1, 10, 10, {costo})"
                        ),
                        {"v": venta_id, "p": producto_id},
                    )
            assert "ck_linea_venta_costo_unit_positivo" in str(exc.value)
    finally:
        engine.dispose()


@needs_pg
def test_downgrade_0008_sin_residuos_y_reupgrade_en_pg(migrated_db) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    engine = create_engine(migrated_db)
    try:
        with engine.begin() as conn:
            _seed_linea_previa(conn, "d8")
    finally:
        engine.dispose()
    command.downgrade(cfg, "-1")
    engine = create_engine(migrated_db)
    try:
        insp = inspect(engine)
        assert "costo_unit" not in {c["name"] for c in insp.get_columns("linea_venta")}
        assert "ix_venta_estado_confirmada_at" not in {
            i["name"] for i in insp.get_indexes("venta")
        }
        assert "ck_linea_venta_costo_unit_positivo" not in {
            c["name"] for c in insp.get_check_constraints("linea_venta")
        }
        # 0007 sigue intacta: la linea y sus checks viven.
        assert "ck_linea_venta_cantidad_positiva" in {
            c["name"] for c in insp.get_check_constraints("linea_venta")
        }
        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT cantidad FROM linea_venta WHERE id = 'l-d8'")
                ).scalar_one()
                == 2
            )
    finally:
        engine.dispose()
    command.upgrade(cfg, "head")
    engine = create_engine(migrated_db)
    try:
        insp = inspect(engine)
        assert "costo_unit" in {c["name"] for c in insp.get_columns("linea_venta")}
        assert "ix_venta_estado_confirmada_at" in {
            i["name"] for i in insp.get_indexes("venta")
        }
    finally:
        engine.dispose()
