"""C-19 grupo 1: la lista y la busqueda de clientes incluyen sus mascotas activas."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import event

from app.modules.clientes.models import Cliente, Mascota
from app.modules.clientes.schemas import ClienteListItem, ClienteListResponse, ClienteResponse
from tests.compras_helpers import login as _login
from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD

CLIENTES_URL = "/api/clientes"
_AHORA = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _base() -> dict:
    return {
        "id": "c1",
        "nombre": "Ana",
        "telefono": None,
        "email": None,
        "direccion": None,
        "activo": True,
        "created_at": _AHORA,
        "updated_at": _AHORA,
    }


# --- 1.2 schemas ---


def test_list_item_extiende_cliente_response_con_mascotas() -> None:
    item = ClienteListItem(**_base(), mascotas=[{"id": "m1", "nombre": "Rex", "tipo": "perro", "activo": True}])
    assert isinstance(item, ClienteResponse)
    assert [(m.nombre, m.tipo) for m in item.mascotas] == [("Rex", "perro")]


def test_list_item_exige_mascotas() -> None:
    with pytest.raises(ValidationError):
        ClienteListItem(**_base())


def test_list_item_rechaza_mascota_con_tipo_invalido() -> None:
    with pytest.raises(ValidationError):
        ClienteListItem(**_base(), mascotas=[{"id": "m1", "nombre": "Rex", "tipo": "pez", "activo": True}])


def test_cliente_response_no_acepta_mascotas() -> None:
    with pytest.raises(ValidationError):
        ClienteResponse(**_base(), mascotas=[])


def test_list_response_usa_list_item() -> None:
    lista = ClienteListResponse(
        total=1, page=1, page_size=20, total_pages=1, items=[{**_base(), "mascotas": []}]
    )
    assert isinstance(lista.items[0], ClienteListItem)


# --- 1.3 servicio + router ---


async def _duena(client) -> dict:
    return await _login(client, DUENA_EMAIL, DUENA_PASSWORD)


async def _cliente(client, headers, nombre="Ana") -> str:
    r = await client.post(CLIENTES_URL, json={"nombre": nombre}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mascota(client, headers, cid, nombre, tipo="perro") -> str:
    r = await client.post(f"{CLIENTES_URL}/{cid}/mascotas", json={"nombre": nombre, "tipo": tipo}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_lista_trae_solo_mascotas_activas_en_orden_de_creacion(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    await _mascota(client, h, cid, "Firulais", "perro")
    baja = await _mascota(client, h, cid, "Vieja", "gato")
    await _mascota(client, h, cid, "Mishi", "gato")
    assert (await client.delete(f"{CLIENTES_URL}/{cid}/mascotas/{baja}", headers=h)).status_code == 204

    items = (await client.get(CLIENTES_URL, headers=h)).json()["items"]

    assert [(m["nombre"], m["tipo"], m["activo"]) for m in items[0]["mascotas"]] == [
        ("Firulais", "perro", True),
        ("Mishi", "gato", True),
    ]
    assert set(items[0]["mascotas"][0]) == {"id", "nombre", "tipo", "activo"}


async def test_lista_sin_mascotas_devuelve_lista_vacia(client) -> None:
    h = await _duena(client)
    await _cliente(client, h)
    items = (await client.get(CLIENTES_URL, headers=h)).json()["items"]
    assert items[0]["mascotas"] == []


async def test_lista_no_mezcla_mascotas_entre_clientes(client) -> None:
    h = await _duena(client)
    ana = await _cliente(client, h, "Ana")
    beto = await _cliente(client, h, "Beto")
    await _mascota(client, h, ana, "DeAna")
    await _mascota(client, h, beto, "DeBeto", "gato")
    items = {i["nombre"]: i for i in (await client.get(CLIENTES_URL, headers=h)).json()["items"]}
    assert [m["nombre"] for m in items["Ana"]["mascotas"]] == ["DeAna"]
    assert [m["nombre"] for m in items["Beto"]["mascotas"]] == ["DeBeto"]


async def test_busqueda_tambien_trae_las_mascotas(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h, "Maria")
    await _mascota(client, h, cid, "Toby")
    items = (await client.get(f"{CLIENTES_URL}/buscar", params={"q": "mari"}, headers=h)).json()["items"]
    assert [m["nombre"] for m in items[0]["mascotas"]] == ["Toby"]


async def test_post_put_y_get_por_id_no_incluyen_mascotas(client) -> None:
    h = await _duena(client)
    creado = await client.post(CLIENTES_URL, json={"nombre": "Ana"}, headers=h)
    cid = creado.json()["id"]
    editado = await client.put(f"{CLIENTES_URL}/{cid}", json={"nombre": "Ana B"}, headers=h)
    leido = await client.get(f"{CLIENTES_URL}/{cid}", headers=h)
    assert "mascotas" not in creado.json()
    assert "mascotas" not in editado.json()
    assert "mascotas" not in leido.json()


async def test_mostrador_ve_las_mascotas_en_la_lista(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    await _mascota(client, d, cid, "Rex")
    m = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    items = (await client.get(CLIENTES_URL, headers=m)).json()["items"]
    assert [x["nombre"] for x in items[0]["mascotas"]] == ["Rex"]


def _contar_consultas_de_mascotas(db_session_factory, llamada) -> int:
    with db_session_factory() as db:
        engine = db.get_bind()
        sentencias: list[str] = []

        def _registrar(conn, cursor, statement, parameters, context, executemany):
            sentencias.append(statement)

        event.listen(engine, "before_cursor_execute", _registrar)
        try:
            llamada(db)
        finally:
            event.remove(engine, "before_cursor_execute", _registrar)
    return sum(1 for s in sentencias if "FROM mascotas" in s)


@pytest.mark.parametrize("cantidad", [1, 5])
def test_una_pagina_ejecuta_una_sola_consulta_de_mascotas(db_session_factory, cantidad) -> None:
    from app.modules.clientes import service

    with db_session_factory() as db:
        for i in range(cantidad):
            c = Cliente(nombre=f"Cliente {i}")
            db.add(c)
            db.flush()
            db.add(Mascota(cliente_id=c.id, nombre=f"M{i}", tipo="perro", created_at=_AHORA))
        db.commit()

    def _llamada(db) -> None:
        items, _ = service.listar_clientes(db, 1, 20)
        por_cliente = service.mascotas_activas_por_cliente(db, [c.id for c in items])
        assert len(por_cliente) == cantidad

    assert _contar_consultas_de_mascotas(db_session_factory, _llamada) == 1


def test_sin_ids_no_consulta_mascotas(db_session_factory) -> None:
    from app.modules.clientes import service

    def _llamada(db) -> None:
        assert service.mascotas_activas_por_cliente(db, []) == {}

    assert _contar_consultas_de_mascotas(db_session_factory, _llamada) == 0
