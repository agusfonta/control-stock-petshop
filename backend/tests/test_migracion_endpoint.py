"""POST /api/migracion/productos (C-08, D11): RBAC, dry-run, confirmacion y errores HTTP."""

import json

import pytest
from sqlalchemy import func, select

from app.models import MovimientoStock, Producto
from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)
from tests.migracion_helpers import xlsx_bytes

URL = "/api/migracion/productos"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ENC = ["sku", "nombre", "costo", "margen_pct", "stock", "distribuidora"]
FILAS = [["a-1", "Uno", 100, 35, 10, "Sur"], ["A-2", "Dos", 200, 50, 0, "Sur"]]


async def login(client, email=DUENA_EMAIL, password=DUENA_PASSWORD):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def subir(client, headers=None, filas=FILAS, enc=ENC, nombre="cat.xlsx", data=None, contenido=None):
    contenido = contenido if contenido is not None else xlsx_bytes(enc, filas)
    return client.post(
        URL, headers=headers or {}, data=data or {}, files={"archivo": (nombre, contenido, XLSX)}
    )


def contar(db_session_factory, modelo):
    with db_session_factory() as db:
        return db.scalar(select(func.count()).select_from(modelo))


async def test_anonimo_recibe_401(client):
    assert (await subir(client)).status_code == 401


async def test_mostrador_recibe_403_sin_analizar(client, db_session_factory):
    h = await login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    assert (await subir(client, h, contenido=b"no es un xlsx")).status_code == 403


async def test_duena_dry_run_por_defecto_devuelve_reporte_sin_escribir(client, db_session_factory):
    r = await subir(client, await login(client))
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["confirmado"] is False and cuerpo["lote_id"] is None
    assert cuerpo["totales"]["crear"] == 2
    assert cuerpo["distribuidoras_a_crear"] == ["Sur"]
    assert contar(db_session_factory, Producto) == 0


async def test_dry_run_con_errores_sigue_siendo_200(client):
    filas = [*FILAS, ["A-3", "Sin costo", 0, 10, 0, None]]
    r = await subir(client, await login(client), filas=filas)
    assert r.status_code == 200 and r.json()["totales"]["errores"] == 1


async def test_duena_confirma_y_crea_productos_con_lote(client, db_session_factory):
    r = await subir(client, await login(client), data={"confirmar": "true"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["confirmado"] is True and len(cuerpo["lote_id"]) == 36
    assert contar(db_session_factory, Producto) == 2
    with db_session_factory() as db:
        mov = db.scalars(select(MovimientoStock)).one()
        assert (mov.tipo, mov.cantidad, mov.ref_id) == ("apertura", 10, cuerpo["lote_id"])


async def test_confirmar_con_errores_es_422_con_el_reporte_y_sin_escrituras(client, db_session_factory):
    filas = [*FILAS, ["A-3", "Sin costo", 0, 10, 0, None]]
    r = await subir(client, await login(client), filas=filas, data={"confirmar": "true"})
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["confirmado"] is False and cuerpo["totales"]["errores"] == 1
    assert [f["fila"] for f in cuerpo["filas"] if f["estado"] == "error"] == [4]
    assert contar(db_session_factory, Producto) == 0


async def test_formato_no_admitido_es_415(client):
    r = await subir(client, await login(client), nombre="catalogo.pdf", contenido=b"%PDF")
    assert r.status_code == 415


async def test_archivo_mayor_a_5_mb_es_413(client):
    grande = b"x" * (5 * 1024 * 1024 + 1)
    r = await subir(client, await login(client), contenido=grande)
    assert r.status_code == 413


@pytest.mark.parametrize("mapeo", ["{no es json", '{"campo_raro": "X"}', '{"costo": ""}', "[1]"])
async def test_mapeo_invalido_es_422(client, mapeo):
    r = await subir(client, await login(client), data={"mapeo": mapeo})
    assert r.status_code == 422


async def test_mapeo_valido_se_aplica(client):
    enc = ["codigo_x", "descr", "Valor compra", "ganancia"]
    mapeo = {"sku": "codigo_x", "nombre": "descr", "costo": "Valor compra"}
    r = await subir(
        client, await login(client), enc=enc, filas=[["a-1", "Uno", 100, 35]],
        data={"mapeo": json.dumps(mapeo)},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["columnas"]["mapeadas"]["costo"] == "Valor compra"
    assert cuerpo["totales"]["errores"] == 0


async def test_catalogo_cambio_es_409(client, monkeypatch, db_session_factory):
    from app.routers import migracion as router_mod
    from app.services.migracion import CatalogoCambio

    def paralelo(*args, **kwargs):
        raise CatalogoCambio("sku creado en paralelo")

    monkeypatch.setattr(router_mod, "importar", paralelo)
    r = await subir(client, await login(client), data={"confirmar": "true"})
    assert r.status_code == 409
    assert contar(db_session_factory, Producto) == 0
