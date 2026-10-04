"""Validacion de schemas Pydantic de distribuidoras (C-06 task 1.2, RED-first).

DistribuidoraCreate/Update estrictos + ListaPrecioDistribuidoraCreate
anidada (sin distribuidora_id en body — va en el path).
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    DistribuidoraCreate,
    DistribuidoraUpdate,
    ListaPrecioDistribuidoraCreate,
)


# --- DistribuidoraCreate ---


def test_distribuidora_create_ok_con_minimos() -> None:
    d = DistribuidoraCreate(nombre="Distri Sur")
    assert d.nombre == "Distri Sur"
    assert d.contacto is None
    assert d.cuit is None
    assert d.condiciones is None


def test_distribuidora_create_ok_con_opcionales() -> None:
    d = DistribuidoraCreate(
        nombre="Distri Sur",
        contacto="Juan 555-1234",
        cuit="30-12345678-9",
        condiciones="pago a 30 dias",
    )
    assert d.cuit == "30-12345678-9"


def test_distribuidora_create_sin_nombre_rechazado() -> None:
    with pytest.raises(ValidationError):
        DistribuidoraCreate()


def test_distribuidora_create_nombre_vacio_rechazado() -> None:
    with pytest.raises(ValidationError):
        DistribuidoraCreate(nombre="  ")


def test_distribuidora_create_campo_extra_rechazado() -> None:
    with pytest.raises(ValidationError):
        DistribuidoraCreate(nombre="X", desconocido="y")


# --- DistribuidoraUpdate (parcial) ---


def test_distribuidora_update_vacio_ok() -> None:
    d = DistribuidoraUpdate()
    assert d.nombre is None
    assert d.condiciones is None


def test_distribuidora_update_nombre_vacio_rechazado() -> None:
    with pytest.raises(ValidationError):
        DistribuidoraUpdate(nombre="  ")


def test_distribuidora_update_condiciones_ok() -> None:
    d = DistribuidoraUpdate(condiciones="pago a 30 dias")
    assert d.condiciones == "pago a 30 dias"


def test_distribuidora_update_campo_extra_rechazado() -> None:
    with pytest.raises(ValidationError):
        DistribuidoraUpdate(nombre="X", activo=True)


# --- ListaPrecioDistribuidoraCreate (anidada, sin distribuidora_id) ---


def test_lista_distribuidora_create_ok() -> None:
    lp = ListaPrecioDistribuidoraCreate(producto_id="p1", costo=800)
    assert lp.producto_id == "p1"
    assert lp.costo == Decimal("800")


def test_lista_distribuidora_create_costo_cero_rechazado() -> None:
    with pytest.raises(ValidationError):
        ListaPrecioDistribuidoraCreate(producto_id="p1", costo=0)


def test_lista_distribuidora_create_costo_negativo_rechazado() -> None:
    with pytest.raises(ValidationError):
        ListaPrecioDistribuidoraCreate(producto_id="p1", costo=-50)


def test_lista_distribuidora_create_con_distribuidora_id_rechazado() -> None:
    """El id de distribuidora va en el path, no en el body (D3)."""
    with pytest.raises(ValidationError):
        ListaPrecioDistribuidoraCreate(
            distribuidora_id="d1", producto_id="p1", costo=800
        )


def test_lista_distribuidora_create_sin_producto_id_rechazado() -> None:
    with pytest.raises(ValidationError):
        ListaPrecioDistribuidoraCreate(costo=800)
