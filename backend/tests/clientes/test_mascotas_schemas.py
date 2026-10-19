"""Schemas de mascotas (C-17 task 2.2, RED-first)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.clientes.schemas import MascotaCreate, MascotaResponse, MascotaUpdate


def test_create_valido() -> None:
    m = MascotaCreate(nombre="Firulais", tipo="perro")
    assert (m.nombre, m.tipo) == ("Firulais", "perro")


def test_create_nombre_se_recorta() -> None:
    assert MascotaCreate(nombre="  Mishi  ", tipo="gato").nombre == "Mishi"


@pytest.mark.parametrize("nombre", ["", "   "])
def test_create_nombre_vacio_rechazado(nombre) -> None:
    with pytest.raises(ValidationError):
        MascotaCreate(nombre=nombre, tipo="perro")


def test_create_nombre_de_100_ok_y_101_rechazado() -> None:
    assert len(MascotaCreate(nombre="a" * 100, tipo="otro").nombre) == 100
    with pytest.raises(ValidationError):
        MascotaCreate(nombre="a" * 101, tipo="otro")


@pytest.mark.parametrize("tipo", ["perro", "gato", "otro"])
def test_create_tipos_permitidos(tipo) -> None:
    assert MascotaCreate(nombre="X", tipo=tipo).tipo == tipo


@pytest.mark.parametrize("tipo", ["dragón", "", "Perro", None])
def test_create_tipo_invalido_rechazado(tipo) -> None:
    with pytest.raises(ValidationError):
        MascotaCreate(nombre="Rex", tipo=tipo)


def test_create_nombre_y_tipo_obligatorios() -> None:
    with pytest.raises(ValidationError):
        MascotaCreate(tipo="perro")
    with pytest.raises(ValidationError):
        MascotaCreate(nombre="Rex")


def test_create_extra_prohibido() -> None:
    with pytest.raises(ValidationError):
        MascotaCreate(nombre="Rex", tipo="perro", raza="mestizo")


def test_update_parcial_y_validaciones() -> None:
    assert MascotaUpdate(tipo="gato").nombre is None
    assert MascotaUpdate(nombre="  Rex ").nombre == "Rex"
    with pytest.raises(ValidationError):
        MascotaUpdate(nombre="  ")
    with pytest.raises(ValidationError):
        MascotaUpdate(nombre=None)
    with pytest.raises(ValidationError):
        MascotaUpdate(tipo="dragón")
    with pytest.raises(ValidationError):
        MascotaUpdate(tipo=None)
    with pytest.raises(ValidationError):
        MascotaUpdate(activo=False)


def test_response_forma() -> None:
    ahora = datetime.now(timezone.utc)
    r = MascotaResponse(id="m1", nombre="Rex", tipo="perro", activo=True)
    assert r.model_dump() == {"id": "m1", "nombre": "Rex", "tipo": "perro", "activo": True}
    with pytest.raises(ValidationError):
        MascotaResponse(id="m1", nombre="Rex", tipo="perro", activo=True, created_at=ahora)
