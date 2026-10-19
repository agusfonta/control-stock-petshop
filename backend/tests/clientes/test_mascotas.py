"""API de mascotas por cliente (C-17 task 2.6, RED-first)."""

from tests.compras_helpers import login as _login
from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)

CLIENTES_URL = "/api/clientes"


async def _duena(client) -> dict:
    return await _login(client, DUENA_EMAIL, DUENA_PASSWORD)


async def _mostrador(client) -> dict:
    return await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)


async def _cliente(client, headers, nombre="Ana") -> str:
    r = await client.post(CLIENTES_URL, json={"nombre": nombre}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _url(cliente_id, mascota_id=None) -> str:
    base = f"{CLIENTES_URL}/{cliente_id}/mascotas"
    return base if mascota_id is None else f"{base}/{mascota_id}"


async def _mascota(client, headers, cid, nombre="Firulais", tipo="perro") -> dict:
    r = await client.post(_url(cid), json={"nombre": nombre, "tipo": tipo}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_mostrador_crea_mascota_201_con_forma_esperada(client) -> None:
    h = await _mostrador(client)
    cid = await _cliente(client, h)
    r = await client.post(_url(cid), json={"nombre": "  Firulais ", "tipo": "perro"}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "nombre", "tipo", "activo"}
    assert (body["nombre"], body["tipo"], body["activo"]) == ("Firulais", "perro", True)


async def test_duena_crea_mascota_201(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    assert (await client.post(_url(cid), json={"nombre": "Mishi", "tipo": "gato"}, headers=h)).status_code == 201


async def test_listado_devuelve_varias_en_orden_de_creacion_para_autenticado(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    await _mascota(client, d, cid, "Firulais", "perro")
    await _mascota(client, d, cid, "Mishi", "gato")
    m = await _mostrador(client)
    r = await client.get(_url(cid), headers=m)
    assert r.status_code == 200
    assert [(x["nombre"], x["tipo"]) for x in r.json()] == [("Firulais", "perro"), ("Mishi", "gato")]


async def test_listado_vacio_es_lista_vacia(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    r = await client.get(_url(cid), headers=d)
    assert r.status_code == 200 and r.json() == []


async def test_anonimo_recibe_401_en_todos_los_endpoints(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    mid = (await _mascota(client, d, cid))["id"]
    assert (await client.get(_url(cid))).status_code == 401
    assert (await client.post(_url(cid), json={"nombre": "X", "tipo": "gato"})).status_code == 401
    assert (await client.put(_url(cid, mid), json={"nombre": "X"})).status_code == 401
    assert (await client.delete(_url(cid, mid))).status_code == 401


async def test_tipo_invalido_o_nombre_vacio_422_y_no_se_crea(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    assert (await client.post(_url(cid), json={"nombre": "Rex", "tipo": "dragón"}, headers=h)).status_code == 422
    assert (await client.post(_url(cid), json={"nombre": "  ", "tipo": "perro"}, headers=h)).status_code == 422
    assert (await client.post(_url(cid), json={"nombre": "Rex", "tipo": "perro", "x": 1}, headers=h)).status_code == 422
    assert (await client.get(_url(cid), headers=h)).json() == []


async def test_crear_o_listar_en_cliente_inexistente_404(client) -> None:
    h = await _duena(client)
    r = await client.post(_url("no-existe"), json={"nombre": "Rex", "tipo": "perro"}, headers=h)
    assert r.status_code == 404
    assert (await client.get(_url("no-existe"), headers=h)).status_code == 404


async def test_duena_actualiza_mascota_200(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    mid = (await _mascota(client, d, cid))["id"]
    r = await client.put(_url(cid, mid), json={"nombre": "Rex", "tipo": "otro"}, headers=d)
    assert r.status_code == 200
    assert (r.json()["nombre"], r.json()["tipo"]) == ("Rex", "otro")
    r = await client.put(_url(cid, mid), json={"tipo": "gato"}, headers=d)
    assert (r.json()["nombre"], r.json()["tipo"]) == ("Rex", "gato")


async def test_mostrador_no_puede_editar_ni_dar_de_baja_403(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    mid = (await _mascota(client, d, cid))["id"]
    m = await _mostrador(client)
    assert (await client.put(_url(cid, mid), json={"nombre": "X"}, headers=m)).status_code == 403
    assert (await client.delete(_url(cid, mid), headers=m)).status_code == 403


async def test_put_con_datos_invalidos_422(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    mid = (await _mascota(client, d, cid))["id"]
    assert (await client.put(_url(cid, mid), json={"tipo": "dragón"}, headers=d)).status_code == 422
    assert (await client.put(_url(cid, mid), json={"nombre": ""}, headers=d)).status_code == 422


async def test_mascota_de_otro_cliente_404_en_put_y_delete(client) -> None:
    d = await _duena(client)
    a, b = await _cliente(client, d), await _cliente(client, d, "Beto")
    mid = (await _mascota(client, d, b))["id"]
    assert (await client.put(_url(a, mid), json={"nombre": "X"}, headers=d)).status_code == 404
    assert (await client.delete(_url(a, mid), headers=d)).status_code == 404
    assert (await client.put(_url(a, "no-existe"), json={"nombre": "X"}, headers=d)).status_code == 404


async def test_delete_204_y_desaparece_del_listado(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    mid = (await _mascota(client, d, cid))["id"]
    await _mascota(client, d, cid, "Mishi", "gato")
    assert (await client.delete(_url(cid, mid), headers=d)).status_code == 204
    assert [x["nombre"] for x in (await client.get(_url(cid), headers=d)).json()] == ["Mishi"]
    # Ya dada de baja: no existe para editar ni volver a borrar.
    assert (await client.delete(_url(cid, mid), headers=d)).status_code == 404
    assert (await client.put(_url(cid, mid), json={"nombre": "X"}, headers=d)).status_code == 404


# --- C-18: cliente dado de baja ---


def _baja_cliente(db_session_factory, cliente_id: str) -> None:
    from app.modules.clientes.models import Cliente

    with db_session_factory() as session:
        session.get(Cliente, cliente_id).activo = False
        session.commit()


async def test_crear_mascota_de_cliente_de_baja_409(client, db_session_factory) -> None:
    h = await _mostrador(client)
    cid = await _cliente(client, h)
    _baja_cliente(db_session_factory, cid)
    r = await client.post(_url(cid), json={"nombre": "Rex", "tipo": "perro"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"] == "cliente dado de baja"
    assert (await client.get(_url(cid), headers=h)).json() == []


async def test_editar_mascota_de_cliente_de_baja_409_y_get_sigue_200(client, db_session_factory) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    m = await _mascota(client, h, cid)
    _baja_cliente(db_session_factory, cid)
    r = await client.put(_url(cid, m["id"]), json={"nombre": "Otro"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"] == "cliente dado de baja"
    listado = await client.get(_url(cid), headers=h)
    assert listado.status_code == 200
    assert [x["nombre"] for x in listado.json()] == ["Firulais"]
