"""Inicializa el esquema de la base segun el motor (C-13 D15).

- SQLite (solo desarrollo/test): crea las tablas desde los modelos.
- PostgreSQL: aplica las migraciones Alembic hasta `head`.

Es idempotente: sobre una base ya inicializada no hace nada destructivo.

Uso (desde backend/):
    python -m scripts.init_db
"""

import os
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_upgrade(url: str) -> None:
    """`alembic upgrade head` contra `url` (env.py lee DATABASE_URL de Settings)."""
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


def _crear_desde_modelos(url: str) -> None:
    from app.core.db import build_engine
    from app.models import Base

    parsed = make_url(url)
    if parsed.database and parsed.database != ":memory:":
        Path(parsed.database).expanduser().resolve().parent.mkdir(
            parents=True, exist_ok=True
        )
    engine = build_engine(url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def init_db(url: str | None = None) -> str:
    """Crea el esquema y devuelve el modo usado: "create_all" o "alembic"."""
    if url is None:
        from app.core.config import get_settings

        url = get_settings().database_url
    if url.startswith("sqlite"):
        _crear_desde_modelos(url)
        return "create_all"
    _alembic_upgrade(url)
    return "alembic"


def main() -> None:
    from app.core.config import get_settings

    url = get_settings().database_url
    modo = init_db(url)
    print(f"init_db ok: {make_url(url).render_as_string(hide_password=True)} ({modo})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - mensaje claro para quien corre el script
        print(f"init_db failed: {exc}", file=sys.stderr)
        raise
