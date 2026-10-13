"""Service de clientes (C-16 D5): logica de acceso a datos fuera del router.

RED-first: el service no existe todavia. Los tests HTTP (`test_clientes*.py`)
son la caracterizacion del comportamiento; estos prueban el contrato del
service con excepciones de dominio (sin HTTP).
"""

import pytest

from app.modules.clientes import service
from app.modules.clientes.models import Cliente
from app.modules.clientes.schemas import ClienteCreate, ClienteUpdate


@pytest.fixture
def db(db_session_factory):
    with db_session_factory() as session:
        yield session


def _crear(db, nombre="Ana Perez", **extra) -> Cliente:
    return service.crear_cliente(db, ClienteCreate(nombre=nombre, **extra))


# --- crear ---


def test_crear_persiste_y_devuelve_el_cliente(db) -> None:
    cliente = _crear(db, telefono="1155551234", email="ana@mail.com")

    assert cliente.id
    assert cliente.activo is True
    assert db.get(Cliente, cliente.id).email == "ana@mail.com"


def test_crear_con_email_de_cliente_activo_lanza_email_en_uso(db) -> None:
    _crear(db, email="ana@mail.com")

    with pytest.raises(service.EmailEnUso):
        _crear(db, nombre="Otra", email="ANA@mail.com")


def test_crear_con_email_de_cliente_dado_de_baja_es_valido(db) -> None:
    viejo = _crear(db, email="ana@mail.com")
    service.desactivar_cliente(db, viejo.id)

    nuevo = _crear(db, nombre="Nueva", email="ana@mail.com")

    assert nuevo.id != viejo.id


def test_crear_sin_email_dos_veces_no_choca(db) -> None:
    _crear(db, nombre="Uno")
    _crear(db, nombre="Dos")

    assert service.listar_clientes(db, 1, 20)[1] == 2


# --- obtener ---


def test_obtener_devuelve_el_cliente(db) -> None:
    creado = _crear(db)

    assert service.obtener_cliente(db, creado.id).nombre == "Ana Perez"


def test_obtener_inexistente_lanza_cliente_no_encontrado(db) -> None:
    with pytest.raises(service.ClienteNoEncontrado):
        service.obtener_cliente(db, "no-existe")


def test_obtener_no_filtra_inactivos(db) -> None:
    creado = _crear(db)
    service.desactivar_cliente(db, creado.id)

    assert service.obtener_cliente(db, creado.id).activo is False


# --- listar / buscar ---


def test_listar_pagina_ordenado_por_nombre_y_excluye_inactivos(db) -> None:
    for nombre in ("Carla", "Alicia", "Beto"):
        _crear(db, nombre=nombre)
    baja = _crear(db, nombre="Zoe")
    service.desactivar_cliente(db, baja.id)

    items, total = service.listar_clientes(db, 1, 2)
    resto, _ = service.listar_clientes(db, 2, 2)

    assert total == 3
    assert [c.nombre for c in items] == ["Alicia", "Beto"]
    assert [c.nombre for c in resto] == ["Carla"]


def test_buscar_por_nombre_sin_acentos_ni_mayusculas(db) -> None:
    _crear(db, nombre="José Ñandú")
    _crear(db, nombre="Maria")

    items, total = service.buscar_clientes(db, "JOSE", 1, 20)

    assert total == 1
    assert items[0].nombre == "José Ñandú"


def test_buscar_por_telefono_ignora_separadores(db) -> None:
    _crear(db, nombre="Tel", telefono="11 5555-1234")
    _crear(db, nombre="Otro", telefono="11 4444-0000")

    items, total = service.buscar_clientes(db, "5555 1234", 1, 20)

    assert total == 1
    assert items[0].nombre == "Tel"


def test_buscar_texto_en_blanco_lanza_busqueda_vacia(db) -> None:
    with pytest.raises(service.BusquedaVacia):
        service.buscar_clientes(db, "   ", 1, 20)


def test_buscar_comodin_porcentaje_no_matchea_todo(db) -> None:
    _crear(db, nombre="Ana")

    _, total = service.buscar_clientes(db, "%", 1, 20)

    assert total == 0


# --- actualizar ---


def test_actualizar_aplica_solo_campos_enviados(db) -> None:
    creado = _crear(db, telefono="1155551234", email="ana@mail.com")

    actualizado = service.actualizar_cliente(db, creado.id, ClienteUpdate(nombre="Ana Maria"))

    assert actualizado.nombre == "Ana Maria"
    assert actualizado.email == "ana@mail.com"
    assert actualizado.telefono == "1155551234"


def test_actualizar_inexistente_lanza_cliente_no_encontrado(db) -> None:
    with pytest.raises(service.ClienteNoEncontrado):
        service.actualizar_cliente(db, "no-existe", ClienteUpdate(nombre="X"))


def test_actualizar_email_de_otro_cliente_lanza_email_en_uso(db) -> None:
    _crear(db, nombre="Uno", email="uno@mail.com")
    dos = _crear(db, nombre="Dos", email="dos@mail.com")

    with pytest.raises(service.EmailEnUso):
        service.actualizar_cliente(db, dos.id, ClienteUpdate(email="uno@mail.com"))


def test_actualizar_con_su_propio_email_no_choca(db) -> None:
    uno = _crear(db, nombre="Uno", email="uno@mail.com")

    actualizado = service.actualizar_cliente(db, uno.id, ClienteUpdate(email="uno@mail.com", nombre="Uno B"))

    assert actualizado.nombre == "Uno B"


# --- desactivar ---


def test_desactivar_hace_soft_delete(db) -> None:
    creado = _crear(db)

    service.desactivar_cliente(db, creado.id)

    assert db.get(Cliente, creado.id).activo is False
    assert service.listar_clientes(db, 1, 20)[1] == 0


def test_desactivar_inexistente_lanza_cliente_no_encontrado(db) -> None:
    with pytest.raises(service.ClienteNoEncontrado):
        service.desactivar_cliente(db, "no-existe")
