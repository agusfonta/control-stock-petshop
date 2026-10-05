"""GET /api/clientes/buscar (C-09 tasks 5.1 y 5.3, RED-first).

Busqueda parcial insensible a mayusculas y acentos sobre nombre y email, y
por digitos sobre telefono; solo activos; paginada. Ver design D6/D7.
"""

from tests.conftest import MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD

CLIENTES_URL = "/api/clientes"
BUSCAR_URL = "/api/clientes/buscar"


async def _headers(client) -> dict:
    response = await client.post(
        "/api/auth/login",
        json={"email": MOSTRADOR_EMAIL, "password": MOSTRADOR_PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _sembrar(db_session_factory, *clientes: dict) -> None:
    """Inserta clientes directo en la base (valores ya normalizados)."""
    from app.models import Cliente

    with db_session_factory() as session:
        for datos in clientes:
            session.add(Cliente(**datos))
        session.commit()


async def _buscar(client, headers, q: str, **params) -> dict:
    response = await client.get(
        BUSCAR_URL, params={"q": q, **params}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def _nombres(body: dict) -> list[str]:
    return [c["nombre"] for c in body["items"]]


async def test_buscar_por_nombre_sin_acentos_ni_mayusculas(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "José Núñez"},
        {"nombre": "Carla Gómez"},
    )
    body = await _buscar(client, await _headers(client), "jose nun")
    assert _nombres(body) == ["José Núñez"]
    assert "saldo_cc" not in body["items"][0]


async def test_buscar_con_acentos_encuentra_nombre_sin_acentos(
    client, db_session_factory
) -> None:
    _sembrar(db_session_factory, {"nombre": "Jose Nunez"})
    body = await _buscar(client, await _headers(client), "JOSÉ NÚÑ")
    assert _nombres(body) == ["Jose Nunez"]


async def test_buscar_por_fragmento_de_telefono_con_separadores(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "Ana", "telefono": "1155551234"},
        {"nombre": "Beto", "telefono": "1144440000"},
    )
    body = await _buscar(client, await _headers(client), "5555-12")
    assert _nombres(body) == ["Ana"]


async def test_buscar_por_email_insensible_a_mayusculas(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "Ana", "email": "ana@mail.com"},
        {"nombre": "Beto", "email": "beto@mail.com"},
    )
    body = await _buscar(client, await _headers(client), "ANA@")
    assert _nombres(body) == ["Ana"]


async def test_buscar_texto_no_matchea_por_telefono(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "Ana", "telefono": "1155551234"},
        {"nombre": "Beto", "telefono": "1144440000"},
    )
    body = await _buscar(client, await _headers(client), "zzz")
    assert body["items"] == []
    assert body["total"] == 0


async def test_buscar_excluye_clientes_dados_de_baja(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "Ana Baja", "activo": False},
        {"nombre": "Ana Activa"},
    )
    body = await _buscar(client, await _headers(client), "ana")
    assert _nombres(body) == ["Ana Activa"]
    solo_baja = await _buscar(client, await _headers(client), "baja")
    assert solo_baja["items"] == []


async def test_buscar_sin_q_422(client) -> None:
    response = await client.get(BUSCAR_URL, headers=await _headers(client))
    assert response.status_code == 422


async def test_buscar_q_en_blanco_422(client) -> None:
    headers = await _headers(client)
    for q in ("", "   "):
        response = await client.get(BUSCAR_URL, params={"q": q}, headers=headers)
        assert response.status_code == 422


async def test_buscar_anonimo_401(client) -> None:
    response = await client.get(BUSCAR_URL, params={"q": "ana"})
    assert response.status_code == 401


async def test_buscar_porcentaje_no_actua_como_comodin(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "Ana"},
        {"nombre": "Descuento 50% Lopez"},
    )
    body = await _buscar(client, await _headers(client), "%")
    assert _nombres(body) == ["Descuento 50% Lopez"]


async def test_buscar_guion_bajo_no_actua_como_comodin(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "Ana"},
        {"nombre": "Ana_Maria"},
    )
    body = await _buscar(client, await _headers(client), "a_m")
    assert _nombres(body) == ["Ana_Maria"]


async def test_buscar_paginado_con_total_ordenado_por_nombre(
    client, db_session_factory
) -> None:
    _sembrar(
        db_session_factory,
        {"nombre": "Marta C"},
        {"nombre": "Marta A"},
        {"nombre": "Marta B"},
        {"nombre": "Otro"},
    )
    headers = await _headers(client)
    pagina1 = await _buscar(client, headers, "marta", page=1, page_size=2)
    assert _nombres(pagina1) == ["Marta A", "Marta B"]
    assert pagina1["total"] == 3
    assert pagina1["total_pages"] == 2
    pagina2 = await _buscar(client, headers, "marta", page=2, page_size=2)
    assert _nombres(pagina2) == ["Marta C"]


# --- Triangulacion (task 5.3) ---


async def test_buscar_no_se_resuelve_como_id(client) -> None:
    response = await client.get(
        BUSCAR_URL, params={"q": "nadie"}, headers=await _headers(client)
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_buscar_nombre_en_mayusculas_acentuadas(
    client, db_session_factory
) -> None:
    _sembrar(db_session_factory, {"nombre": "ÁLVAREZ ÑANDÚ"})
    headers = await _headers(client)
    assert _nombres(await _buscar(client, headers, "alvarez")) == ["ÁLVAREZ ÑANDÚ"]
    assert _nombres(await _buscar(client, headers, "nandu")) == ["ÁLVAREZ ÑANDÚ"]
