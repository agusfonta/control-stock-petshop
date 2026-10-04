"""Job Redis + GET /api/stock/alertas (C-05 task 4.1, RED-first).

Cubre spec scenarios: resumen coincide con el filtro, vacio total=0,
fallback a DB con Redis caido, TTL por env STOCK_ALERT_TTL_S default
60s. En RED fallan: no existe ni el worker ni el endpoint.
"""

import pytest
import redis as redis_lib

from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD
from tests.test_productos_crud import _login, _producto_payload


async def _crear(client, headers, **overrides):
    response = await client.post(
        "/api/productos", json=_producto_payload(**overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def test_resumen_coincide_con_filtro(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-R1", stock_actual=1, stock_minimo=5)
    await _crear(client, headers, sku="STK-R2", stock_actual=5, stock_minimo=5)
    await _crear(client, headers, sku="STK-R3", stock_actual=0, stock_minimo=3)
    await _crear(client, headers, sku="STK-R4", stock_actual=20, stock_minimo=5)
    alertas = (await client.get("/api/stock/alertas", headers=headers)).json()
    filtrados = (
        await client.get("/api/stock?bajo_minimo=true", headers=headers)
    ).json()
    assert alertas["total_bajo_minimo"] == 3
    assert {i["sku"] for i in alertas["items"]} == {
        i["sku"] for i in filtrados["items"]
    } == {"STK-R1", "STK-R2", "STK-R3"}


async def test_sin_bajo_minimo_total_cero(client) -> None:
    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-R5", stock_actual=20, stock_minimo=5)
    response = await client.get("/api/stock/alertas", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_bajo_minimo"] == 0
    assert body["items"] == []


async def test_alertas_anonimo_401(client) -> None:
    response = await client.get("/api/stock/alertas")
    assert response.status_code == 401


async def test_alertas_sin_redis_fallback_a_db(
    client, fake_redis, monkeypatch
) -> None:
    from app.workers.stock_alerts import ALERTAS_KEY

    headers = await _login(client, DUENA_EMAIL, DUENA_PASSWORD)
    await _crear(client, headers, sku="STK-R6", stock_actual=1, stock_minimo=5)

    def _caido(*args, **kwargs):
        raise redis_lib.exceptions.ConnectionError("redis caido")

    monkeypatch.setattr(fake_redis, "smembers", _caido)
    monkeypatch.setattr(fake_redis, "pipeline", _caido)
    response = await client.get("/api/stock/alertas", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_bajo_minimo"] == 1
    assert body["items"][0]["sku"] == "STK-R6"
    assert ALERTAS_KEY == "stock:bajo_minimo"


def test_job_recalcula_set_con_ttl_default_60(
    db_session_factory, seed_users, fake_redis
) -> None:
    import os

    from app.workers.stock_alerts import ALERTAS_KEY, recalcular_alertas

    os.environ.pop("STOCK_ALERT_TTL_S", None)
    from app.core.config import Settings

    ttl = Settings().stock_alert_ttl_s
    assert ttl == 60
    with db_session_factory() as session:
        from app.models import Producto

        session.add(
            Producto(
                sku="STK-J1",
                nombre="Bajo minimo",
                costo=100,
                stock_actual=1,
                stock_minimo=5,
            )
        )
        session.add(
            Producto(
                sku="STK-J2",
                nombre="Ok",
                costo=100,
                stock_actual=20,
                stock_minimo=5,
            )
        )
        session.commit()
        ids = recalcular_alertas(session, fake_redis, ttl_s=ttl)
        assert len(ids) == 1
        assert fake_redis.smembers(ALERTAS_KEY) == set(ids)
        assert fake_redis.ttl(ALERTAS_KEY) == 60


def test_job_ttl_por_env(fake_redis, monkeypatch) -> None:
    monkeypatch.setenv("STOCK_ALERT_TTL_S", "5")
    from app.core.config import Settings

    assert Settings().stock_alert_ttl_s == 5
