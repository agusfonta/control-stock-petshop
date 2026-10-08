"""Validacion de schemas Pydantic de productos (C-04 task 2.2).

Campos requeridos, tipos correctos, valores negativos rechazados y SKU
pattern. Todos los modelos usan extra="forbid" + strict=True.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    BusquedaResponse,
    MargenMinimoRequest,
    ProductoCreate,
    ProductoResponse,
    PaginacionResponse,
)


def _producto_create_payload(**overrides):
    payload = {
        "sku": "SKU-001",
        "nombre": "Alimento Perro 20kg",
        "costo": 1000,
        "margen_pct": 0.5,
    }
    payload.update(overrides)
    return payload


# --- ProductoCreate: campos requeridos ---


def test_producto_create_ok_con_minimos_requeridos() -> None:
    p = ProductoCreate(**_producto_create_payload())
    assert p.sku == "SKU-001"
    assert p.costo == Decimal("1000")
    assert p.margen_pct == Decimal("0.5")
    assert p.unidad == "unidad"
    assert p.stock_actual == 0
    assert p.stock_minimo == 0


def test_producto_create_default_opcionales() -> None:
    p = ProductoCreate(sku="SKU-1", nombre="X", costo=100)
    assert p.marca is None
    assert p.categoria is None
    assert p.distribuidora_default_id is None


def test_producto_create_sin_sku_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(nombre="X", costo=100)


def test_producto_create_sin_nombre_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(sku="SKU-1", costo=100)


def test_producto_create_sin_costo_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(sku="SKU-1", nombre="X")


# --- ProductoCreate: tipos correctos ---


def test_producto_create_costo_como_str_aceptado() -> None:
    p = ProductoCreate(**_producto_create_payload(costo="1000.50"))
    assert p.costo == Decimal("1000.50")


def test_producto_create_costo_como_float_aceptado() -> None:
    p = ProductoCreate(**_producto_create_payload(costo=1000.5))
    assert p.costo == Decimal("1000.5")


def test_producto_create_costo_como_bool_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(costo=True))


def test_producto_create_unidad_invalida_rechazada() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(unidad="kilo"))


def test_producto_create_stock_actual_negativo_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(stock_actual=-1))


# --- ProductoCreate: valores negativos rechazados ---


def test_producto_create_costo_negativo_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(costo=-100))


def test_producto_create_costo_cero_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(costo=0))


def test_producto_create_margen_negativo_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(margen_pct=-0.5))


# --- ProductoCreate: SKU pattern ---


def test_producto_create_sku_con_espacios_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(sku="SKU 001"))


def test_producto_create_sku_con_caracter_especial_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(sku="SKU/001"))


def test_producto_create_sku_valido_con_guion_y_guion_bajo() -> None:
    p = ProductoCreate(**_producto_create_payload(sku="SKU_001-ABC"))
    assert p.sku == "SKU_001-ABC"


# --- ProductoCreate: extra="forbid" ---


def test_producto_create_campo_extra_rechazado() -> None:
    with pytest.raises(ValidationError):
        ProductoCreate(**_producto_create_payload(descripcion="extra"))


# --- ProductoUpdate: parcial ---


def test_producto_update_vacio_ok() -> None:
    from app.schemas import ProductoUpdate

    p = ProductoUpdate()
    assert p.sku is None
    assert p.costo is None


def test_producto_update_costo_negativo_rechazado() -> None:
    from app.schemas import ProductoUpdate

    with pytest.raises(ValidationError):
        ProductoUpdate(costo=-5)


# --- MargenMinimoRequest ---


def test_margen_minimo_ok() -> None:
    m = MargenMinimoRequest(margen_pct=0.35, stock_minimo=5)
    assert m.margen_pct == Decimal("0.35")
    assert m.stock_minimo == 5


def test_margen_minimo_vacio_ok() -> None:
    m = MargenMinimoRequest()
    assert m.margen_pct is None
    assert m.stock_minimo is None


def test_margen_minimo_margen_negativo_rechazado() -> None:
    with pytest.raises(ValidationError):
        MargenMinimoRequest(margen_pct=-0.5)


def test_margen_minimo_stock_negativo_rechazado() -> None:
    with pytest.raises(ValidationError):
        MargenMinimoRequest(stock_minimo=-1)


def test_margen_minimo_campo_extra_rechazado() -> None:
    with pytest.raises(ValidationError):
        MargenMinimoRequest(margen_pct=0.5, stock_actual=3)


# --- PaginacionResponse / BusquedaResponse ---


def test_paginacion_response_ok() -> None:
    r = PaginacionResponse(total=50, page=2, page_size=20, total_pages=3)
    assert r.total == 50
    assert r.total_pages == 3


def test_paginacion_response_total_pages_cero_ok() -> None:
    r = PaginacionResponse(total=0, page=1, page_size=20, total_pages=0)
    assert r.total_pages == 0


def test_busqueda_response_con_items() -> None:
    item = ProductoResponse(
        id="p1",
        sku="SKU-1",
        nombre="X",
        marca=None,
        categoria=None,
        unidad="unidad",
        costo=Decimal("100"),
        margen_pct=Decimal("0.5"),
        precio_venta=Decimal("150"),
        stock_actual=0,
        stock_minimo=0,
        distribuidora_default_id=None,
        activo=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    r = BusquedaResponse(
        total=1, page=1, page_size=20, total_pages=1, items=[item]
    )
    assert len(r.items) == 1
    assert r.items[0].precio_venta == Decimal("150")


def test_busqueda_response_items_default_vacio() -> None:
    r = BusquedaResponse(total=0, page=1, page_size=20, total_pages=0)
    assert r.items == []
