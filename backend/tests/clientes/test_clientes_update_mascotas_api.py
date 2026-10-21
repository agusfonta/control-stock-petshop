"""C-19 task 2.4: PUT /api/clientes/{id} con `mascotas` (reemplazo atomico)."""

import pytest

from tests.compras_helpers import login as _login
from tests.conftest import DUENA_EMAIL, DUENA_PASSWORD, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD

CLIENTES_URL = "/api/clientes"


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


async def _lista_mascotas(client, headers, cid) -> list[tuple[str, str]]:
    r = await client.get(f"{CLIENTES_URL}/{cid}/mascotas", headers=headers)
    return [(m["nombre"], m["tipo"]) for m in r.json()]


async def _en_tabla(client, headers, cid) -> list[tuple[str, str]]:
    items = (await client.get(CLIENTES_URL, params={"page_size": 100}, headers=headers)).json()["items"]
    return [(m["nombre"], m["tipo"]) for i in items if i["id"] == cid for m in i["mascotas"]]


async def test_editar_sin_mascotas_no_las_toca(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    await _mascota(client, h, cid, "Rex")
    r = await client.put(f"{CLIENTES_URL}/{cid}", json={"nombre": "Ana B"}, headers=h)
    assert r.status_code == 200 and r.json()["nombre"] == "Ana B"
    assert await _lista_mascotas(client, h, cid) == [("Rex", "perro")]


async def test_reemplazo_mixto_actualiza_crea_y_da_de_baja(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    rex = await _mascota(client, h, cid, "Rex")
    await _mascota(client, h, cid, "Mishi", "gato")
    r = await client.put(
        f"{CLIENTES_URL}/{cid}",
        json={
            "nombre": "Ana B",
            "mascotas": [{"id": rex, "nombre": "Rexy", "tipo": "otro"}, {"nombre": "Nuevo", "tipo": "gato"}],
        },
        headers=h,
    )
    assert r.status_code == 200
    assert "mascotas" not in r.json() and r.json()["nombre"] == "Ana B"
    esperado = [("Rexy", "otro"), ("Nuevo", "gato")]
    assert await _lista_mascotas(client, h, cid) == esperado
    assert await _en_tabla(client, h, cid) == esperado


async def test_lista_vacia_da_de_baja_todas(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    await _mascota(client, h, cid, "Rex")
    r = await client.put(f"{CLIENTES_URL}/{cid}", json={"mascotas": []}, headers=h)
    assert r.status_code == 200
    assert await _lista_mascotas(client, h, cid) == []
    assert await _en_tabla(client, h, cid) == []


async def test_id_ajeno_404_sin_cambios(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h, "Ana")
    otro = await _cliente(client, h, "Beto")
    await _mascota(client, h, cid, "Rex")
    ajena = await _mascota(client, h, otro, "Ajena", "gato")
    r = await client.put(
        f"{CLIENTES_URL}/{cid}",
        json={"nombre": "Cambiado", "mascotas": [{"id": ajena, "nombre": "X", "tipo": "gato"}]},
        headers=h,
    )
    assert r.status_code == 404 and r.json()["detail"] == "mascota no encontrada"
    assert (await client.get(f"{CLIENTES_URL}/{cid}", headers=h)).json()["nombre"] == "Ana"
    assert await _lista_mascotas(client, h, cid) == [("Rex", "perro")]
    assert await _lista_mascotas(client, h, otro) == [("Ajena", "gato")]


async def test_id_de_mascota_dada_de_baja_404(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    baja = await _mascota(client, h, cid, "Vieja")
    await client.delete(f"{CLIENTES_URL}/{cid}/mascotas/{baja}", headers=h)
    r = await client.put(
        f"{CLIENTES_URL}/{cid}", json={"mascotas": [{"id": baja, "nombre": "X", "tipo": "gato"}]}, headers=h
    )
    assert r.status_code == 404


_MAL = [
    pytest.param({"mascotas": None}, id="null"),
    pytest.param({"mascotas": [{"nombre": "Rex", "tipo": "pez"}]}, id="tipo-invalido"),
    pytest.param({"mascotas": [{"nombre": "  ", "tipo": "perro"}]}, id="nombre-vacio"),
    pytest.param(
        {"mascotas": [{"id": "a", "nombre": "A", "tipo": "gato"}, {"id": "a", "nombre": "B", "tipo": "gato"}]},
        id="ids-repetidos",
    ),
    pytest.param({"mascotas": [{"nombre": f"M{i}", "tipo": "gato"} for i in range(21)]}, id="mas-de-20"),
    pytest.param({"mascotas": [{"nombre": "Rex", "tipo": "perro", "activo": False}]}, id="campo-extra"),
]


@pytest.mark.parametrize("payload", _MAL)
async def test_payload_invalido_422_y_no_cambia_nada(client, payload) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    await _mascota(client, h, cid, "Rex")
    r = await client.put(f"{CLIENTES_URL}/{cid}", json={"nombre": "Cambiado", **payload}, headers=h)
    assert r.status_code == 422
    assert (await client.get(f"{CLIENTES_URL}/{cid}", headers=h)).json()["nombre"] == "Ana"
    assert await _lista_mascotas(client, h, cid) == [("Rex", "perro")]


async def test_maximo_20_mascotas_es_aceptado(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    r = await client.put(
        f"{CLIENTES_URL}/{cid}", json={"mascotas": [{"nombre": f"M{i}", "tipo": "gato"} for i in range(20)]}, headers=h
    )
    assert r.status_code == 200
    assert len(await _lista_mascotas(client, h, cid)) == 20


async def test_cliente_de_baja_con_mascotas_409_y_sin_mascotas_sigue_editable(client) -> None:
    h = await _duena(client)
    cid = await _cliente(client, h)
    await _mascota(client, h, cid, "Rex")
    assert (await client.delete(f"{CLIENTES_URL}/{cid}", headers=h)).status_code == 204

    r = await client.put(f"{CLIENTES_URL}/{cid}", json={"nombre": "Nuevo", "mascotas": []}, headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "cliente dado de baja"
    assert (await client.get(f"{CLIENTES_URL}/{cid}", headers=h)).json()["nombre"] == "Ana"
    assert await _lista_mascotas(client, h, cid) == [("Rex", "perro")]

    ok = await client.put(f"{CLIENTES_URL}/{cid}", json={"nombre": "Nuevo"}, headers=h)
    assert ok.status_code == 200 and ok.json()["nombre"] == "Nuevo"


async def test_mostrador_no_puede_editar_mascotas_403(client) -> None:
    d = await _duena(client)
    cid = await _cliente(client, d)
    await _mascota(client, d, cid, "Rex")
    m = await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)
    r = await client.put(f"{CLIENTES_URL}/{cid}", json={"mascotas": []}, headers=m)
    assert r.status_code == 403
    assert await _lista_mascotas(client, d, cid) == [("Rex", "perro")]


async def test_cliente_inexistente_404(client) -> None:
    h = await _duena(client)
    r = await client.put(f"{CLIENTES_URL}/no-existe", json={"mascotas": []}, headers=h)
    assert r.status_code == 404 and r.json()["detail"] == "cliente no encontrado"
