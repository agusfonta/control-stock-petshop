"""Schemas de compras (C-07)."""

from datetime import date, datetime
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
    serialize_money,
)

# --- C-07: pedidos de compra, entradas y pagos a distribuidoras ---

ESTADO_PEDIDO_LITERAL = Literal["pendiente", "recibido", "cancelado"]


METODO_PAGO_LITERAL = Literal["efectivo", "transferencia", "cheque", "otro"]


def _coerce_fecha(v: object) -> object:
    """Convierte 'YYYY-MM-DD' (JSON) a date antes del check estricto.

    Con strict=True Pydantic v2 solo acepta instancias date en modo python;
    el JSON llega como str. Un str mal formado levanta ValueError (-> 422).
    """
    if isinstance(v, str):
        return date.fromisoformat(v)
    return v


class LineaPedidoCreate(BaseModel):
    """Linea de POST /api/compras/pedidos: sin costo, lo fija el servidor (D6)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    producto_id: str = Field(min_length=1)
    cantidad: int = Field(gt=0)


class PedidoCreate(BaseModel):
    """Alta de pedido de compra (POST /api/compras/pedidos)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    distribuidora_id: str = Field(min_length=1)
    lineas: list[LineaPedidoCreate] = Field(min_length=1, max_length=100)
    notas: str | None = Field(default=None, max_length=500)

    @field_validator("lineas", mode="after")
    @classmethod
    def _sin_productos_repetidos(
        cls, v: list[LineaPedidoCreate]
    ) -> list[LineaPedidoCreate]:
        ids = [linea.producto_id for linea in v]
        if len(ids) != len(set(ids)):
            raise ValueError("producto_id repetido en el pedido")
        return v


class LineaPedidoResponse(BaseModel):
    """Linea de pedido con su costo pactado y subtotal (cantidad x costo)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    producto_id: str = Field(min_length=1)
    cantidad: int
    costo_unitario: Decimal
    subtotal: Decimal

    @field_serializer("costo_unitario", "subtotal")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class EntradaStockResponse(BaseModel):
    """Entrada de stock generada al recibir un pedido (append-only)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    producto_id: str = Field(min_length=1)
    cantidad: int
    costo_unitario: Decimal
    usuario_id: str = Field(min_length=1)
    created_at: datetime

    @field_serializer("costo_unitario")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class PedidoResponse(BaseModel):
    """Pedido de compra con lineas, total estimado y, si se recibio, entradas."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    distribuidora_id: str = Field(min_length=1)
    estado: ESTADO_PEDIDO_LITERAL
    usuario_id: str = Field(min_length=1)
    notas: str | None
    recibido_at: datetime | None
    recibido_por_id: str | None
    total_estimado: Decimal
    lineas: list[LineaPedidoResponse] = Field(default_factory=list)
    entradas: list[EntradaStockResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_serializer("total_estimado")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class PedidoListResponse(PaginacionResponse):
    """Envelope paginado de GET /api/compras/pedidos."""

    items: list[PedidoResponse] = Field(default_factory=list)


class PagoCreate(BaseModel):
    """Alta de pago a distribuidora (POST /api/compras/pagos, solo duena).

    Sin pedido_id (RN-CP-03: el pago no se asocia a pedidos; extra=forbid
    lo rechaza). monto acotado a la precision de la columna Numeric(12,2).
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    distribuidora_id: str = Field(min_length=1)
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    metodo: METODO_PAGO_LITERAL
    fecha: date | None = None
    nota: str | None = Field(default=None, max_length=500)

    @field_validator("monto", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return coerce_decimal(v)

    @field_validator("fecha", mode="before")
    @classmethod
    def _fecha(cls, v: object) -> object:
        return _coerce_fecha(v)


class PagoResponse(BaseModel):
    """Pago a distribuidora expuesto via API."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    distribuidora_id: str = Field(min_length=1)
    monto: Decimal
    metodo: METODO_PAGO_LITERAL
    fecha: date
    nota: str | None
    usuario_id: str = Field(min_length=1)
    activo: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("monto")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class PagoListResponse(PaginacionResponse):
    """Envelope paginado de GET /api/compras/pagos."""

    items: list[PagoResponse] = Field(default_factory=list)


class CuentaDistribuidoraResponse(BaseModel):
    """Cuenta simple: total recibido - total pagado = saldo (positivo = deuda)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    distribuidora_id: str = Field(min_length=1)
    total_recibido: Decimal
    total_pagado: Decimal
    saldo: Decimal

    @field_serializer("total_recibido", "total_pagado", "saldo")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)
