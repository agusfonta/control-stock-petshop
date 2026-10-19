"""Schemas de stock con alertas y ajustes (C-05)."""

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
)
from app.modules.productos.schemas import ProductoResponse

# --- C-05: stock con alertas y ajustes auditables ---


class StockItem(BaseModel):
    """Producto activo con badge derivado bajo_minimo (RN-ST-01).

    bajo_minimo es derivado (stock_actual <= stock_minimo, decision D3),
    nunca una columna: evita drift entre columna y realidad.
    """

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
    bajo_minimo: bool
    distribuidora_default_id: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("costo", "margen_pct", "precio_venta")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        if v == v.to_integral_value():
            return int(v)
        return float(v)


class StockListResponse(PaginacionResponse):
    """Envelope paginado de GET /api/stock."""

    items: list[StockItem] = Field(default_factory=list)


class AjusteStockRequest(BaseModel):
    """Body de POST /api/productos/{id}/ajustar (RN-ST-02/03).

    motivo obligatorio no vacio: sin motivo no hay trazabilidad.
    cantidad_delta admite 0? No: un ajuste de 0 no cambia nada y
    genera ruido en el ledger, se rechaza con ge/le excluyendo el 0
    via validacion de distinto-de-cero.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    cantidad_delta: int = Field(strict=True)
    motivo: str = Field(min_length=1, max_length=500)

    @field_validator("motivo", mode="before")
    @classmethod
    def _motivo_no_vacio(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("motivo no puede estar vacio")
        return v

    @field_validator("cantidad_delta", mode="after")
    @classmethod
    def _delta_no_cero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("cantidad_delta no puede ser 0")
        return v


class MovimientoResponse(BaseModel):
    """Movimiento de stock expuesto via API (ledger, sin update/delete)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    producto_id: str = Field(min_length=1)
    tipo: Literal["venta", "entrada", "ajuste", "apertura"]
    cantidad: int
    stock_previo: int
    stock_nuevo: int
    ref_id: str | None
    motivo: str | None
    usuario_id: str = Field(min_length=1)
    created_at: datetime


class AjusteStockResponse(BaseModel):
    """Respuesta de POST /api/productos/{id}/ajustar: producto + movimiento."""

    model_config = ConfigDict(extra="forbid", strict=True)

    producto: ProductoResponse
    movimiento: MovimientoResponse


class AlertasResponse(BaseModel):
    """Resumen de GET /api/stock/alertas para reposicion (Flujo 2)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    total_bajo_minimo: int = Field(ge=0)
    items: list[StockItem] = Field(default_factory=list)
