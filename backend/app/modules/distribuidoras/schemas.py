"""Schemas de distribuidoras y listas de precios (C-06)."""

from datetime import datetime
from decimal import Decimal

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
    nombre_no_vacio,
)


class DistribuidoraCreate(BaseModel):
    """Alta de distribuidora (POST /api/distribuidoras)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    nombre: str = Field(min_length=1, max_length=200)
    contacto: str | None = Field(default=None, max_length=200)
    cuit: str | None = Field(default=None, max_length=20)
    condiciones: str | None = Field(default=None, max_length=500)

    @field_validator("nombre", mode="before")
    @classmethod
    def _nombre(cls, v: object) -> object:
        return nombre_no_vacio(v)


class DistribuidoraUpdate(BaseModel):
    """Actualizacion parcial de distribuidora (PUT /api/distribuidoras/{id})."""

    model_config = ConfigDict(extra="forbid", strict=True)

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    contacto: str | None = Field(default=None, max_length=200)
    cuit: str | None = Field(default=None, max_length=20)
    condiciones: str | None = Field(default=None, max_length=500)

    @field_validator("nombre", mode="before")
    @classmethod
    def _nombre(cls, v: object) -> object:
        if v is None:
            return v
        return nombre_no_vacio(v)


class DistribuidoraResponse(BaseModel):
    """Distribuidora expuesta via API."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    nombre: str
    contacto: str | None
    cuit: str | None
    condiciones: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime


class DistribuidoraListResponse(PaginacionResponse):
    """Envelope paginado de GET /api/distribuidoras (como BusquedaResponse)."""

    items: list[DistribuidoraResponse] = Field(default_factory=list)


class ListaPrecioDistribuidoraCreate(BaseModel):
    """Alta de costo en una lista (POST /api/distribuidoras/{id}/listas).

    Sin distribuidora_id en body (D3): va en el path.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    producto_id: str = Field(min_length=1)
    costo: Decimal = Field(gt=0)

    @field_validator("costo", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return coerce_decimal(v)


class ListaPrecioUpdate(BaseModel):
    """Actualizacion del costo de una entrada (PUT .../listas/{producto_id})."""

    model_config = ConfigDict(extra="forbid", strict=True)

    costo: Decimal = Field(gt=0)

    @field_validator("costo", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return coerce_decimal(v)


class ListaPrecioResponse(BaseModel):
    """Entrada de lista de precios expuesta via API."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    distribuidora_id: str = Field(min_length=1)
    producto_id: str = Field(min_length=1)
    costo: Decimal
    activo: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("costo")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        if v == v.to_integral_value():
            return int(v)
        return float(v)


class CompararFila(BaseModel):
    """Un origen de costo con su precio sugerido recalculado (RN-PR-01)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    distribuidora_id: str = Field(min_length=1)
    distribuidora_nombre: str = Field(min_length=1)
    costo: Decimal
    precio_sugerido: Decimal

    @field_serializer("costo", "precio_sugerido")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        if v == v.to_integral_value():
            return int(v)
        return float(v)


class CompararResponse(BaseModel):
    """Respuesta de GET /api/distribuidoras/comparar (solo lectura)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    producto_id: str = Field(min_length=1)
    filas: list[CompararFila] = Field(default_factory=list)
