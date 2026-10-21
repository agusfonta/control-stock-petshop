"""C-19 task 2.3: actualizar_cliente aplica datos + mascotas en una transaccion."""

import pytest

from app.modules.clientes import service
from app.modules.clientes.models import Cliente, Mascota
from app.modules.clientes.schemas import ClienteCreate, ClienteUpdate, MascotaCreate


@pytest.fixture
def db(db_session_factory):
    with db_session_factory() as session:
        yield session


def _cliente(db, nombre="Ana", *mascotas: tuple[str, str]) -> tuple[Cliente, list[Mascota]]:
    cliente = service.crear_cliente(db, ClienteCreate(nombre=nombre))
    creadas = [service.crear_mascota(db, cliente.id, MascotaCreate(nombre=n, tipo=t)) for n, t in mascotas]
    return cliente, creadas


def _upd(**campos) -> ClienteUpdate:
    return ClienteUpdate.model_validate(campos)


def _activas(db, cliente_id) -> list[tuple[str, str]]:
    return [(m.nombre, m.tipo) for m in service.listar_mascotas(db, cliente_id)]


def test_sin_mascotas_en_el_payload_no_las_toca(db) -> None:
    cliente, _ = _cliente(db, "Ana", ("Rex", "perro"))
    service.actualizar_cliente(db, cliente.id, _upd(nombre="Ana B"))
    assert _activas(db, cliente.id) == [("Rex", "perro")]
    assert db.get(Cliente, cliente.id).nombre == "Ana B"


def test_con_id_actualiza_sin_id_crea_y_las_omitidas_se_dan_de_baja(db) -> None:
    cliente, (rex, mishi) = _cliente(db, "Ana", ("Rex", "perro"), ("Mishi", "gato"))
    service.actualizar_cliente(
        db,
        cliente.id,
        _upd(
            nombre="Ana B",
            mascotas=[{"id": rex.id, "nombre": "Rexy", "tipo": "otro"}, {"nombre": "Nuevo", "tipo": "gato"}],
        ),
    )
    assert _activas(db, cliente.id) == [("Rexy", "otro"), ("Nuevo", "gato")]
    assert db.get(Mascota, mishi.id).activo is False
    assert db.get(Mascota, rex.id).id == rex.id
    assert db.get(Cliente, cliente.id).nombre == "Ana B"


def test_lista_vacia_da_de_baja_todas(db) -> None:
    cliente, (rex, mishi) = _cliente(db, "Ana", ("Rex", "perro"), ("Mishi", "gato"))
    service.actualizar_cliente(db, cliente.id, _upd(mascotas=[]))
    assert _activas(db, cliente.id) == []
    assert db.get(Mascota, rex.id).activo is False and db.get(Mascota, mishi.id).activo is False


def test_solo_mascotas_sin_datos_del_cliente(db) -> None:
    cliente, (rex,) = _cliente(db, "Ana", ("Rex", "perro"))
    cambio = _upd(mascotas=[{"id": rex.id, "nombre": "R", "tipo": "gato"}])
    resultado = service.actualizar_cliente(db, cliente.id, cambio)
    assert resultado.nombre == "Ana"
    assert _activas(db, cliente.id) == [("R", "gato")]


@pytest.mark.parametrize("caso", ["inexistente", "ajena", "de_baja"])
def test_id_invalido_lanza_mascota_no_encontrada_con_rollback_total(db, caso) -> None:
    cliente, (rex,) = _cliente(db, "Ana", ("Rex", "perro"))
    otro, (ajena,) = _cliente(db, "Beto", ("Ajena", "gato"))
    baja = service.crear_mascota(db, cliente.id, MascotaCreate(nombre="Vieja", tipo="gato"))
    service.desactivar_mascota(db, cliente.id, baja.id)
    id_malo = {"inexistente": "no-existe", "ajena": ajena.id, "de_baja": baja.id}[caso]

    with pytest.raises(service.MascotaNoEncontrada):
        service.actualizar_cliente(
            db,
            cliente.id,
            _upd(
                nombre="Cambiado",
                mascotas=[
                    {"id": rex.id, "nombre": "Cambiada", "tipo": "otro"},
                    {"id": id_malo, "nombre": "X", "tipo": "gato"},
                ],
            ),
        )

    db.expire_all()
    assert db.get(Cliente, cliente.id).nombre == "Ana"
    assert _activas(db, cliente.id) == [("Rex", "perro")]
    assert _activas(db, otro.id) == [("Ajena", "gato")]


def test_falla_a_mitad_deja_todo_como_estaba(db, monkeypatch) -> None:
    cliente, _ = _cliente(db, "Ana", ("Rex", "perro"))

    class Boom(Exception):
        pass

    def _falla(*args, **kwargs):
        raise Boom

    monkeypatch.setattr(service, "_agregar_mascota", _falla)

    with pytest.raises(Boom):
        service.actualizar_cliente(
            db, cliente.id, _upd(nombre="Cambiado", mascotas=[{"nombre": "Nueva", "tipo": "gato"}])
        )

    db.expire_all()
    assert db.get(Cliente, cliente.id).nombre == "Ana"
    assert _activas(db, cliente.id) == [("Rex", "perro")]


def test_email_en_uso_no_modifica_mascotas(db) -> None:
    service.crear_cliente(db, ClienteCreate(nombre="Otro", email="o@mail.com"))
    cliente, _ = _cliente(db, "Ana", ("Rex", "perro"))
    with pytest.raises(service.EmailEnUso):
        service.actualizar_cliente(db, cliente.id, _upd(email="o@mail.com", mascotas=[]))
    assert _activas(db, cliente.id) == [("Rex", "perro")]


def test_mascotas_sobre_cliente_de_baja_lanza_cliente_inactivo_sin_cambios(db) -> None:
    cliente, _ = _cliente(db, "Ana", ("Rex", "perro"))
    service.desactivar_cliente(db, cliente.id)
    with pytest.raises(service.ClienteInactivo):
        service.actualizar_cliente(db, cliente.id, _upd(nombre="Nuevo", mascotas=[]))
    db.expire_all()
    assert db.get(Cliente, cliente.id).nombre == "Ana"
    assert _activas(db, cliente.id) == [("Rex", "perro")]


def test_cliente_de_baja_sigue_editable_sin_mascotas(db) -> None:
    cliente, _ = _cliente(db, "Ana", ("Rex", "perro"))
    service.desactivar_cliente(db, cliente.id)
    editado = service.actualizar_cliente(db, cliente.id, _upd(nombre="Ana B"))
    assert editado.nombre == "Ana B"
    assert _activas(db, cliente.id) == [("Rex", "perro")]


def test_cliente_inexistente_lanza_cliente_no_encontrado(db) -> None:
    with pytest.raises(service.ClienteNoEncontrado):
        service.actualizar_cliente(db, "no-existe", _upd(mascotas=[]))
