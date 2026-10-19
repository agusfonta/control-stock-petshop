"""Adaptadores de entorno de desarrollo (C-13 B1, tasks 1.2/1.3, RED-first).

CORS configurable, `REDIS_URL=memory://` solo en dev/test, singleton
fakeredis en `get_redis` y conexion SQLite apta para el servidor de desarrollo.
No cambia ningun contrato de API ni comportamiento de auth.
"""

import threading

import httpx
import pytest
from pydantic import ValidationError

ORIGEN_VITE = "http://localhost:5173"
ORIGEN_AJENO = "http://evil.example"


async def _preflight(app, origin: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        return await ac.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )


async def test_preflight_origen_vite_permitido() -> None:
    from app.main import create_app

    resp = await _preflight(create_app(), ORIGEN_VITE)

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEN_VITE
    assert resp.headers["access-control-allow-credentials"] == "true"


async def test_preflight_origen_desconocido_sin_headers_cors() -> None:
    from app.main import create_app

    resp = await _preflight(create_app(), ORIGEN_AJENO)

    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


async def test_cors_origins_configurable_lista_separada_por_comas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("CORS_ORIGINS", "http://uno.test, http://dos.test")
    get_settings.cache_clear()
    try:
        app = create_app()
        permitido = await _preflight(app, "http://dos.test")
        vite = await _preflight(app, ORIGEN_VITE)
    finally:
        get_settings.cache_clear()

    assert permitido.headers["access-control-allow-origin"] == "http://dos.test"
    assert "access-control-allow-origin" not in vite.headers


def test_cors_origins_lista_parseada() -> None:
    from app.core.config import Settings

    settings = Settings(
        _env_file=None, cors_origins="http://uno.test, http://dos.test,,"
    )

    assert settings.cors_origins_list == ["http://uno.test", "http://dos.test"]
    assert Settings(_env_file=None).cors_origins_list == [ORIGEN_VITE]


def test_memory_redis_rechazado_fuera_de_dev_test() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError, match="memory://"):
        Settings(
            _env_file=None,
            env="prod",
            redis_url="memory://",
            secret_key="x" * 40,
        )


@pytest.mark.parametrize("entorno", ["dev", "test"])
def test_memory_redis_permitido_en_dev_y_test(entorno: str) -> None:
    from app.core.config import Settings

    settings = Settings(_env_file=None, env=entorno, redis_url="memory://")

    assert settings.redis_url == "memory://"


def test_get_redis_memory_devuelve_el_mismo_cliente_en_memoria() -> None:
    from app.core.config import Settings
    from app.deps import get_redis

    settings = Settings(_env_file=None, env="dev", redis_url="memory://")

    primero = get_redis(settings)
    segundo = get_redis(settings)

    assert primero is segundo
    primero.set("c13:clave", "valor")
    assert segundo.get("c13:clave") == "valor"
    primero.delete("c13:clave")


def test_get_redis_url_real_no_usa_el_singleton_en_memoria() -> None:
    from app.core.config import Settings
    from app.deps import get_redis

    memoria = get_redis(Settings(_env_file=None, env="dev", redis_url="memory://"))
    real = get_redis(
        Settings(_env_file=None, env="dev", redis_url="redis://localhost:6379/0")
    )

    assert real is not memoria


def test_engine_sqlite_permite_uso_desde_otro_hilo(tmp_path) -> None:
    from app.core.db import build_engine

    engine = build_engine(f"sqlite:///{tmp_path / 'hilos.db'}")
    raw = engine.raw_connection()
    errores: list[BaseException] = []

    def _usar_en_otro_hilo() -> None:
        try:
            raw.driver_connection.execute("select 1").fetchone()
        except BaseException as exc:  # noqa: BLE001 - se reporta en el assert
            errores.append(exc)

    hilo = threading.Thread(target=_usar_en_otro_hilo)
    hilo.start()
    hilo.join()
    raw.close()
    engine.dispose()

    assert errores == []


def test_engine_postgres_no_recibe_connect_args_sqlite() -> None:
    from app.core.db import build_engine

    engine = build_engine("postgresql://u:p@localhost:5432/x")

    assert engine.url.get_backend_name() == "postgresql"
    engine.dispose()
