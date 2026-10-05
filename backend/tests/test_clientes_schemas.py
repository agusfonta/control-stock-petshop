"""Schemas de clientes (C-09 task 2.1, RED-first).

Validacion y normalizacion en el borde; `saldo_cc` reservado (D8).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import (
    ClienteCreate,
    ClienteListResponse,
    ClienteResponse,
    ClienteUpdate,
)

# --- ClienteCreate ---


def test_create_solo_nombre_es_valido() -> None:
    cliente = ClienteCreate(nombre="Juan")
    assert cliente.nombre == "Juan"
    assert cliente.telefono is None
    assert cliente.email is None
    assert cliente.direccion is None


def test_create_nombre_se_recorta() -> None:
    assert ClienteCreate(nombre="  Ana Pérez  ").nombre == "Ana Pérez"


@pytest.mark.parametrize("datos", [{}, {"nombre": ""}, {"nombre": "   "}])
def test_create_nombre_ausente_o_en_blanco_falla(datos: dict) -> None:
    with pytest.raises(ValidationError):
        ClienteCreate(**datos)


def test_create_email_se_normaliza_a_minusculas_y_recorta() -> None:
    assert ClienteCreate(nombre="Ana", email="Ana@Mail.com ").email == "ana@mail.com"


@pytest.mark.parametrize("email", ["no-es-email", "a@b", "a b@c.com"])
def test_create_email_invalido_falla(email: str) -> None:
    with pytest.raises(ValidationError):
        ClienteCreate(nombre="Ana", email=email)


def test_create_telefono_se_normaliza() -> None:
    assert ClienteCreate(nombre="Ana", telefono="11 5555-1234").telefono == "1155551234"
    assert (
        ClienteCreate(nombre="Ana", telefono="+54 (11) 5555.1234").telefono
        == "+541155551234"
    )


@pytest.mark.parametrize("telefono", ["abc", "12345", "1" * 21])
def test_create_telefono_invalido_falla(telefono: str) -> None:
    with pytest.raises(ValidationError):
        ClienteCreate(nombre="Ana", telefono=telefono)


@pytest.mark.parametrize("campo", ["telefono", "email", "direccion"])
@pytest.mark.parametrize("vacio", ["", "  "])
def test_create_opcional_en_blanco_queda_none(campo: str, vacio: str) -> None:
    cliente = ClienteCreate(nombre="Ana", **{campo: vacio})
    assert getattr(cliente, campo) is None


def test_create_direccion_se_recorta() -> None:
    assert ClienteCreate(nombre="Ana", direccion=" Calle 1 ").direccion == "Calle 1"


def test_create_saldo_cc_es_rechazado() -> None:
    with pytest.raises(ValidationError):
        ClienteCreate(nombre="Ana", saldo_cc=500)


def test_create_campo_desconocido_es_rechazado() -> None:
    with pytest.raises(ValidationError):
        ClienteCreate(nombre="Ana", rol="duena")


# --- ClienteUpdate ---


def test_update_vacio_es_valido() -> None:
    assert ClienteUpdate().model_dump(exclude_unset=True) == {}


def test_update_parcial_solo_incluye_lo_enviado() -> None:
    cambios = ClienteUpdate(telefono="11-4444-0000").model_dump(exclude_unset=True)
    assert cambios == {"telefono": "1144440000"}


def test_update_nombre_nulo_falla() -> None:
    with pytest.raises(ValidationError):
        ClienteUpdate(nombre=None)


def test_update_nombre_en_blanco_falla() -> None:
    with pytest.raises(ValidationError):
        ClienteUpdate(nombre="  ")


def test_update_email_en_blanco_borra_el_dato() -> None:
    cambios = ClienteUpdate(email="").model_dump(exclude_unset=True)
    assert cambios == {"email": None}


def test_update_saldo_cc_es_rechazado() -> None:
    with pytest.raises(ValidationError):
        ClienteUpdate(saldo_cc=500)


# --- ClienteResponse / ClienteListResponse ---


def test_response_no_tiene_saldo_cc() -> None:
    assert "saldo_cc" not in ClienteResponse.model_fields


def test_response_rechaza_saldo_cc() -> None:
    ahora = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ClienteResponse(
            id="c1",
            nombre="Ana",
            telefono=None,
            email=None,
            direccion=None,
            activo=True,
            created_at=ahora,
            updated_at=ahora,
            saldo_cc=0,
        )


def test_list_response_extiende_paginacion() -> None:
    lista = ClienteListResponse(total=0, page=1, page_size=20, total_pages=0)
    assert lista.items == []
