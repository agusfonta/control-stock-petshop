"""CRUD de clientes via API (C-09 tasks 3.1 y 4.1, RED-first).

Alta: duena y mostrador. Edicion/baja: solo duena. Lectura: cualquier
usuario activo. Baja = soft-delete (activo=False). `saldo_cc` reservado (D8).
"""

from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)

CLIENTES_URL = "/api/clientes"


def _cliente_payload(**overrides):
    payload = {"nombre": "Ana Pérez"}
    payload.update(overrides)
    return payload


async def _login(client, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _duena(client) -> dict:
    return await _login(client, DUENA_EMAIL, DUENA_PASSWORD)


async def _mostrador(client) -> dict:
    return await _login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)


async def _crear(client, headers, **overrides) -> dict:
    response = await client.post(
        CLIENTES_URL, json=_cliente_payload(**overrides), headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Crear ---


async def test_duena_crea_cliente_completo_201_normalizado(client) -> None:
    headers = await _duena(client)
    response = await client.post(
        CLIENTES_URL,
        json={
            "nombre": "Ana Pérez",
            "telefono": "11 5555-1234",
            "email": "Ana@Mail.com",
            "direccion": "Calle 1",
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["nombre"] == "Ana Pérez"
    assert body["telefono"] == "1155551234"
    assert body["email"] == "ana@mail.com"
    assert body["direccion"] == "Calle 1"
    assert body["activo"] is True
    assert body["id"]
    assert body["created_at"]
    assert body["updated_at"]


async def test_mostrador_crea_cliente_solo_nombre_201(client) -> None:
    headers = await _mostrador(client)
    response = await client.post(
        CLIENTES_URL, json={"nombre": "Juan"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["nombre"] == "Juan"
    assert body["telefono"] is None
    assert body["email"] is None
    assert body["direccion"] is None


async def test_crear_cliente_telefono_internacional_201(client) -> None:
    headers = await _mostrador(client)
    response = await client.post(
        CLIENTES_URL,
        json=_cliente_payload(telefono="+54 (11) 5555.1234"),
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["telefono"] == "+541155551234"


async def test_crear_cliente_opcionales_en_blanco_quedan_nulos(client) -> None:
    headers = await _mostrador(client)
    response = await client.post(
        CLIENTES_URL,
        json=_cliente_payload(email="", direccion="  "),
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["email"] is None
    assert response.json()["direccion"] is None


async def test_crear_cliente_anonimo_401(client) -> None:
    response = await client.post(CLIENTES_URL, json=_cliente_payload())
    assert response.status_code == 401


async def test_crear_cliente_nombre_en_blanco_422(client) -> None:
    headers = await _mostrador(client)
    for payload in ({}, {"nombre": "   "}):
        response = await client.post(CLIENTES_URL, json=payload, headers=headers)
        assert response.status_code == 422
    listado = await client.get(CLIENTES_URL, headers=headers)
    assert listado.json()["total"] == 0


async def test_crear_cliente_email_o_telefono_invalidos_422(client) -> None:
    headers = await _mostrador(client)
    for extra in ({"email": "no-es-email"}, {"telefono": "abc"}, {"telefono": "123"}):
        response = await client.post(
            CLIENTES_URL, json=_cliente_payload(**extra), headers=headers
        )
        assert response.status_code == 422


async def test_crear_cliente_con_saldo_cc_422(client) -> None:
    headers = await _duena(client)
    response = await client.post(
        CLIENTES_URL, json=_cliente_payload(saldo_cc=500), headers=headers
    )
    assert response.status_code == 422
    listado = await client.get(CLIENTES_URL, headers=headers)
    assert listado.json()["total"] == 0


async def test_crear_cliente_email_duplicado_case_insensitive_409(client) -> None:
    headers = await _mostrador(client)
    await _crear(client, headers, email="ana@mail.com")
    response = await client.post(
        CLIENTES_URL,
        json=_cliente_payload(nombre="Otra", email="ANA@mail.com"),
        headers=headers,
    )
    assert response.status_code == 409
    listado = await client.get(CLIENTES_URL, headers=headers)
    assert listado.json()["total"] == 1


async def test_crear_cliente_telefono_repetido_201(client) -> None:
    headers = await _mostrador(client)
    await _crear(client, headers, telefono="1155551234")
    response = await client.post(
        CLIENTES_URL,
        json=_cliente_payload(nombre="Hermana", telefono="1155551234"),
        headers=headers,
    )
    assert response.status_code == 201


async def test_crear_cliente_nombre_repetido_201(client) -> None:
    headers = await _mostrador(client)
    await _crear(client, headers, nombre="Juan")
    response = await client.post(
        CLIENTES_URL, json={"nombre": "Juan"}, headers=headers
    )
    assert response.status_code == 201


# --- Listar ---


async def test_listar_paginado_solo_activos_ordenado_por_nombre(
    client, db_session_factory
) -> None:
    from app.models import Cliente

    headers = await _mostrador(client)
    for nombre in ("Carla", "Ana", "Beto"):
        await _crear(client, headers, nombre=nombre)
    with db_session_factory() as session:
        session.add(Cliente(nombre="Aaron", activo=False))
        session.commit()

    pagina1 = await client.get(
        CLIENTES_URL, params={"page": 1, "page_size": 2}, headers=headers
    )
    assert pagina1.status_code == 200
    body = pagina1.json()
    assert [c["nombre"] for c in body["items"]] == ["Ana", "Beto"]
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 2

    pagina2 = await client.get(
        CLIENTES_URL, params={"page": 2, "page_size": 2}, headers=headers
    )
    assert [c["nombre"] for c in pagina2.json()["items"]] == ["Carla"]


async def test_listar_vacio_devuelve_total_cero(client) -> None:
    headers = await _mostrador(client)
    response = await client.get(CLIENTES_URL, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["total_pages"] == 0


async def test_listar_anonimo_401(client) -> None:
    response = await client.get(CLIENTES_URL)
    assert response.status_code == 401


# --- Obtener ---


async def test_obtener_cliente_por_id_200(client) -> None:
    headers = await _mostrador(client)
    creado = await _crear(client, headers, telefono="1155551234")
    response = await client.get(f"{CLIENTES_URL}/{creado['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json() == creado


async def test_obtener_cliente_inexistente_404(client) -> None:
    headers = await _mostrador(client)
    response = await client.get(
        f"{CLIENTES_URL}/no-existe-este-id", headers=headers
    )
    assert response.status_code == 404


async def test_obtener_cliente_anonimo_401(client) -> None:
    response = await client.get(f"{CLIENTES_URL}/cualquier-id")
    assert response.status_code == 401


async def test_respuestas_de_cliente_no_exponen_saldo_cc(client) -> None:
    headers = await _mostrador(client)
    creado = await _crear(client, headers)
    assert "saldo_cc" not in creado
    detalle = await client.get(f"{CLIENTES_URL}/{creado['id']}", headers=headers)
    assert "saldo_cc" not in detalle.json()
    listado = await client.get(CLIENTES_URL, headers=headers)
    assert all("saldo_cc" not in item for item in listado.json()["items"])


# --- Clientes dados de baja (triangulacion D5/D9) ---


def _dar_de_baja(db_session_factory, cliente_id: str) -> None:
    from app.models import Cliente

    with db_session_factory() as session:
        session.get(Cliente, cliente_id).activo = False
        session.commit()


async def test_email_de_cliente_dado_de_baja_es_reutilizable_201(
    client, db_session_factory
) -> None:
    headers = await _mostrador(client)
    viejo = await _crear(client, headers, email="ana@mail.com")
    _dar_de_baja(db_session_factory, viejo["id"])
    response = await client.post(
        CLIENTES_URL,
        json=_cliente_payload(nombre="Ana Nueva", email="ana@mail.com"),
        headers=headers,
    )
    assert response.status_code == 201


async def test_obtener_cliente_inactivo_200_con_activo_false(
    client, db_session_factory
) -> None:
    headers = await _mostrador(client)
    creado = await _crear(client, headers)
    _dar_de_baja(db_session_factory, creado["id"])
    response = await client.get(f"{CLIENTES_URL}/{creado['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["activo"] is False


# --- Editar (solo duena) ---


async def test_duena_edita_telefono_200_normalizado_resto_intacto(client) -> None:
    headers = await _duena(client)
    creado = await _crear(
        client,
        headers,
        telefono="1155551234",
        email="ana@mail.com",
        direccion="Calle 1",
    )
    response = await client.put(
        f"{CLIENTES_URL}/{creado['id']}",
        json={"telefono": "11-4444-0000"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["telefono"] == "1144440000"
    assert body["nombre"] == "Ana Pérez"
    assert body["email"] == "ana@mail.com"
    assert body["direccion"] == "Calle 1"


async def test_editar_nombre_nulo_422_sin_cambios(client) -> None:
    headers = await _duena(client)
    creado = await _crear(client, headers)
    response = await client.put(
        f"{CLIENTES_URL}/{creado['id']}", json={"nombre": None}, headers=headers
    )
    assert response.status_code == 422
    detalle = await client.get(f"{CLIENTES_URL}/{creado['id']}", headers=headers)
    assert detalle.json()["nombre"] == "Ana Pérez"


async def test_editar_con_saldo_cc_422_saldo_persistido_en_cero(
    client, db_session_factory
) -> None:
    from app.models import Cliente

    headers = await _duena(client)
    creado = await _crear(client, headers)
    response = await client.put(
        f"{CLIENTES_URL}/{creado['id']}", json={"saldo_cc": 500}, headers=headers
    )
    assert response.status_code == 422
    with db_session_factory() as session:
        assert session.get(Cliente, creado["id"]).saldo_cc == 0


async def test_editar_con_email_de_otro_activo_409_sin_cambios(client) -> None:
    headers = await _duena(client)
    await _crear(client, headers, nombre="Ana", email="ana@mail.com")
    otro = await _crear(client, headers, nombre="Beto", email="beto@mail.com")
    response = await client.put(
        f"{CLIENTES_URL}/{otro['id']}",
        json={"email": "ANA@mail.com"},
        headers=headers,
    )
    assert response.status_code == 409
    detalle = await client.get(f"{CLIENTES_URL}/{otro['id']}", headers=headers)
    assert detalle.json()["email"] == "beto@mail.com"


async def test_mostrador_no_puede_editar_403_sin_cambios(client) -> None:
    duena = await _duena(client)
    creado = await _crear(client, duena, telefono="1155551234")
    mostrador = await _mostrador(client)
    response = await client.put(
        f"{CLIENTES_URL}/{creado['id']}",
        json={"telefono": "1144440000"},
        headers=mostrador,
    )
    assert response.status_code == 403
    detalle = await client.get(f"{CLIENTES_URL}/{creado['id']}", headers=duena)
    assert detalle.json()["telefono"] == "1155551234"


async def test_editar_cliente_inexistente_404(client) -> None:
    headers = await _duena(client)
    response = await client.put(
        f"{CLIENTES_URL}/no-existe-este-id", json={"nombre": "X"}, headers=headers
    )
    assert response.status_code == 404


async def test_editar_anonimo_401(client) -> None:
    response = await client.put(f"{CLIENTES_URL}/cualquier-id", json={"nombre": "X"})
    assert response.status_code == 401


# --- Baja (soft-delete, solo duena) ---


async def test_duena_da_de_baja_204_soft_delete_fila_presente(
    client, db_session_factory
) -> None:
    from app.models import Cliente

    headers = await _duena(client)
    creado = await _crear(client, headers)
    response = await client.delete(f"{CLIENTES_URL}/{creado['id']}", headers=headers)
    assert response.status_code == 204
    with db_session_factory() as session:
        fila = session.get(Cliente, creado["id"])
        assert fila is not None
        assert fila.activo is False
    listado = await client.get(CLIENTES_URL, headers=headers)
    assert listado.json()["total"] == 0


async def test_mostrador_no_puede_dar_de_baja_403_sigue_activo(client) -> None:
    duena = await _duena(client)
    creado = await _crear(client, duena)
    mostrador = await _mostrador(client)
    response = await client.delete(
        f"{CLIENTES_URL}/{creado['id']}", headers=mostrador
    )
    assert response.status_code == 403
    detalle = await client.get(f"{CLIENTES_URL}/{creado['id']}", headers=duena)
    assert detalle.json()["activo"] is True


async def test_baja_de_cliente_inexistente_404(client) -> None:
    headers = await _duena(client)
    response = await client.delete(
        f"{CLIENTES_URL}/no-existe-este-id", headers=headers
    )
    assert response.status_code == 404


async def test_baja_anonimo_401(client) -> None:
    response = await client.delete(f"{CLIENTES_URL}/cualquier-id")
    assert response.status_code == 401


async def test_editar_manteniendo_el_mismo_email_propio_200(client) -> None:
    headers = await _duena(client)
    creado = await _crear(client, headers, email="ana@mail.com")
    response = await client.put(
        f"{CLIENTES_URL}/{creado['id']}",
        json={"nombre": "Ana María", "email": "Ana@Mail.com"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["nombre"] == "Ana María"
    assert response.json()["email"] == "ana@mail.com"


async def test_editar_email_en_blanco_lo_borra_200(client) -> None:
    headers = await _duena(client)
    creado = await _crear(client, headers, email="ana@mail.com")
    response = await client.put(
        f"{CLIENTES_URL}/{creado['id']}", json={"email": ""}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["email"] is None
