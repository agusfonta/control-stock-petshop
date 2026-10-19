"""Service de mascotas (C-17 task 2.5, RED-first): sin HTTP, errores de dominio."""

import pytest

from app.modules.clientes import service
from app.modules.clientes.models import Mascota
from app.modules.clientes.schemas import ClienteCreate, MascotaCreate, MascotaUpdate


@pytest.fixture
def db(db_session_factory):
    with db_session_factory() as session:
        yield session


def _cliente(db, nombre="Ana"):
    return service.crear_cliente(db, ClienteCreate(nombre=nombre))


def _mascota(db, cliente, nombre="Firulais", tipo="perro") -> Mascota:
    return service.crear_mascota(db, cliente.id, MascotaCreate(nombre=nombre, tipo=tipo))


def test_crear_persiste_y_devuelve_la_mascota(db) -> None:
    c = _cliente(db)
    m = _mascota(db, c)
    assert m.id and m.activo is True
    assert db.get(Mascota, m.id).cliente_id == c.id


def test_crear_en_cliente_inexistente_lanza_cliente_no_encontrado(db) -> None:
    with pytest.raises(service.ClienteNoEncontrado):
        service.crear_mascota(db, "no-existe", MascotaCreate(nombre="X", tipo="gato"))


def test_listar_devuelve_activas_en_orden_de_creacion_solo_del_cliente(db) -> None:
    a, b = _cliente(db), _cliente(db, "Beto")
    m1 = _mascota(db, a, "Firulais")
    m2 = _mascota(db, a, "Mishi", "gato")
    _mascota(db, b, "Otra")
    baja = _mascota(db, a, "Baja")
    service.desactivar_mascota(db, a.id, baja.id)
    assert [m.id for m in service.listar_mascotas(db, a.id)] == [m1.id, m2.id]


def test_listar_cliente_inexistente_lanza_cliente_no_encontrado(db) -> None:
    with pytest.raises(service.ClienteNoEncontrado):
        service.listar_mascotas(db, "no-existe")


def test_actualizar_cambia_solo_los_campos_enviados(db) -> None:
    c = _cliente(db)
    m = _mascota(db, c)
    service.actualizar_mascota(db, c.id, m.id, MascotaUpdate(tipo="gato"))
    assert (m.nombre, m.tipo) == ("Firulais", "gato")
    service.actualizar_mascota(db, c.id, m.id, MascotaUpdate(nombre="Rex"))
    assert (m.nombre, m.tipo) == ("Rex", "gato")


def test_actualizar_mascota_de_otro_cliente_lanza_mascota_no_encontrada(db) -> None:
    a, b = _cliente(db), _cliente(db, "Beto")
    m = _mascota(db, b)
    with pytest.raises(service.MascotaNoEncontrada):
        service.actualizar_mascota(db, a.id, m.id, MascotaUpdate(nombre="X"))


def test_actualizar_mascota_dada_de_baja_lanza_mascota_no_encontrada(db) -> None:
    c = _cliente(db)
    m = _mascota(db, c)
    service.desactivar_mascota(db, c.id, m.id)
    with pytest.raises(service.MascotaNoEncontrada):
        service.actualizar_mascota(db, c.id, m.id, MascotaUpdate(nombre="X"))


def test_desactivar_es_baja_logica(db) -> None:
    c = _cliente(db)
    m = _mascota(db, c)
    service.desactivar_mascota(db, c.id, m.id)
    assert db.get(Mascota, m.id).activo is False


def test_desactivar_inexistente_u_otro_cliente_lanza_mascota_no_encontrada(db) -> None:
    a, b = _cliente(db), _cliente(db, "Beto")
    m = _mascota(db, b)
    with pytest.raises(service.MascotaNoEncontrada):
        service.desactivar_mascota(db, a.id, m.id)
    with pytest.raises(service.MascotaNoEncontrada):
        service.desactivar_mascota(db, a.id, "no-existe")


def test_cliente_inexistente_prevalece_sobre_mascota(db) -> None:
    with pytest.raises(service.ClienteNoEncontrado):
        service.desactivar_mascota(db, "no-existe", "x")


# --- C-18: cliente dado de baja ---


def test_crear_en_cliente_de_baja_lanza_cliente_inactivo_y_no_crea(db) -> None:
    c = _cliente(db)
    service.desactivar_cliente(db, c.id)
    with pytest.raises(service.ClienteInactivo):
        _mascota(db, c)
    assert db.query(Mascota).filter(Mascota.cliente_id == c.id).count() == 0


def test_actualizar_en_cliente_de_baja_lanza_cliente_inactivo_y_no_modifica(db) -> None:
    c = _cliente(db)
    m = _mascota(db, c)
    service.desactivar_cliente(db, c.id)
    with pytest.raises(service.ClienteInactivo):
        service.actualizar_mascota(db, c.id, m.id, MascotaUpdate(nombre="Otro"))
    db.refresh(m)
    assert m.nombre == "Firulais"


def test_listar_en_cliente_de_baja_sigue_permitido(db) -> None:
    c = _cliente(db)
    m = _mascota(db, c)
    service.desactivar_cliente(db, c.id)
    assert [x.id for x in service.listar_mascotas(db, c.id)] == [m.id]
