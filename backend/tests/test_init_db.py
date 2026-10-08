"""init_db (C-13 B1, task 1.4, RED-first): crea el esquema segun el motor."""

from sqlalchemy import create_engine, inspect


def test_sqlite_crea_las_tablas_desde_los_modelos(tmp_path) -> None:
    from scripts.init_db import init_db

    url = f"sqlite:///{tmp_path / 'init.db'}"

    modo = init_db(url)

    tablas = set(inspect(create_engine(url)).get_table_names())
    assert modo == "create_all"
    assert {"usuarios", "productos", "venta", "pedido_compra", "linea_venta"} <= tablas


def test_sqlite_es_idempotente(tmp_path) -> None:
    from scripts.init_db import init_db

    url = f"sqlite:///{tmp_path / 'init.db'}"

    init_db(url)
    init_db(url)

    assert "productos" in inspect(create_engine(url)).get_table_names()


def test_postgres_usa_alembic_upgrade_head(monkeypatch) -> None:
    from scripts import init_db as modulo

    llamadas: list[tuple[str, str]] = []
    monkeypatch.setattr(
        modulo, "_alembic_upgrade", lambda url: llamadas.append(("head", url))
    )

    modo = modulo.init_db("postgresql://u:p@localhost:5432/x")

    assert modo == "alembic"
    assert llamadas == [("head", "postgresql://u:p@localhost:5432/x")]
