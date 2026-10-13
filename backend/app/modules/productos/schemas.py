"""Schemas del catalogo de productos (C-04)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from app.core.schemas import (
    PaginacionResponse,
    coerce_decimal,
)

# --- C-04: catalogo de productos ---

SKU_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"


UNIDAD_LITERAL = Literal["unidad", "bolsa", "caja"]


class ProductoCreate(BaseModel):
    """Alta de producto (POST /api/productos). precio_venta se calcula solo."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sku: str = Field(pattern=SKU_PATTERN, min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=200)
    marca: str | None = Field(default=None, max_length=100)
    categoria: str | None = Field(default=None, max_length=100)
    unidad: UNIDAD_LITERAL = "unidad"
    costo: Decimal = Field(gt=0)
    margen_pct: Decimal = Field(default=0, ge=0)
    stock_actual: int = Field(default=0, ge=0)
    stock_minimo: int = Field(default=0, ge=0)
    distribuidora_default_id: str | None = None

    @field_validator("costo", "margen_pct", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return coerce_decimal(v)


class ProductoUpdate(BaseModel):
    """Actualizacion parcial de producto (PUT /api/productos/{id}).

    Sin stock_actual (C-05 decision D2, RN-ST-03): el stock solo muta
    via POST /ajustar con su movimiento. Con extra="forbid", enviar
    stock_actual responde 422 sin alterar nada.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    sku: str | None = Field(default=None, pattern=SKU_PATTERN, max_length=50)
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    marca: str | None = Field(default=None, max_length=100)
    categoria: str | None = Field(default=None, max_length=100)
    unidad: UNIDAD_LITERAL | None = None
    costo: Decimal | None = Field(default=None, gt=0)
    margen_pct: Decimal | None = Field(default=None, ge=0)
    stock_minimo: int | None = Field(default=None, ge=0)
    distribuidora_default_id: str | None = None

    @field_validator("costo", "margen_pct", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return coerce_decimal(v)


class ProductoResponse(BaseModel):
    """Producto expuesto via API (precio_venta calculado, RN-PR-01)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    sku: str
    nombre: str
    marca: str | None
    categoria: str | None
    unidad: str
    costo: Decimal
    margen_pct: Decimal
    precio_venta: Decimal
    stock_actual: int
    stock_minimo: int
    distribuidora_default_id: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("costo", "margen_pct", "precio_venta")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        """Emite Decimal como numero JSON (int si es entero, float si no).

        Pydantic v2 serializa Decimal a string por defecto; para la API
        monetaria queremos numeros. int cuando no hay decimales para no
        ensenar 2000.00 como 2000.0.
        """
        if v == v.to_integral_value():
            return int(v)
        return float(v)


class MargenMinimoRequest(BaseModel):
    """PATCH /api/productos/{id}/margen-minimo (solo duena)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    margen_pct: Decimal | None = Field(default=None, ge=0)
    stock_minimo: int | None = Field(default=None, ge=0)

    @field_validator("margen_pct", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return coerce_decimal(v)


class BusquedaResponse(PaginacionResponse):
    """Envelope de listado/busqueda: items + metadata de paginacion."""

    items: list[ProductoResponse] = Field(default_factory=list)
