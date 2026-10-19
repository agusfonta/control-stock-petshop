"""Schemas de ventas (C-10)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    AwareDatetime,
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

# --- C-10: ventas de mostrador (precio y total los fija el servidor, D5) ---

ESTADO_VENTA_LITERAL = Literal["borrador", "confirmada", "anulada"]


METODO_PAGO_VENTA_LITERAL = Literal["efectivo", "transferencia", "mp", "tarjeta"]


UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


MAX_PAGOS_VENTA = 5


def _recortar(v: object) -> object:
    """Recorta strings antes de validar largo (un blanco queda vacio => 422)."""
    return v.strip() if isinstance(v, str) else v


class LineaVentaIn(BaseModel):
    """Linea de POST /api/ventas: sin precio ni subtotal, los fija el servidor."""

    model_config = ConfigDict(extra="forbid", strict=True)

    producto_id: str = Field(min_length=1)
    cantidad: int = Field(gt=0)


class VentaCreate(BaseModel):
    """Alta de venta en borrador (POST /api/ventas).

    idempotency_key: UUID canonico generado por el POS (D8); se normaliza a
    minusculas para que la misma clave en otra capitalizacion sea la misma
    clave. Sin precio/total/estado/vendedor: extra=forbid los rechaza (D5).
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    idempotency_key: str = Field(pattern=UUID_PATTERN)
    cliente_id: str | None = Field(default=None, min_length=1)
    lineas: list[LineaVentaIn] = Field(min_length=1, max_length=100)

    @field_validator("idempotency_key", mode="after")
    @classmethod
    def _clave_en_minusculas(cls, v: str) -> str:
        return v.lower()

    @field_validator("lineas", mode="after")
    @classmethod
    def _sin_productos_repetidos(
        cls, v: list[LineaVentaIn]
    ) -> list[LineaVentaIn]:
        ids = [linea.producto_id for linea in v]
        if len(ids) != len(set(ids)):
            raise ValueError("producto_id repetido en la venta")
        return v


class PagoVentaIn(BaseModel):
    """Pago de POST /api/ventas/{id}/confirmar (D10).

    monto acotado a la precision de Numeric(12,2). ref_mp opcional (la
    regla "solo con metodo mp" la aplica el servicio: 422, y la base).
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    metodo: METODO_PAGO_VENTA_LITERAL
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    ref_mp: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("monto", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return coerce_decimal(v)

    @field_validator("ref_mp", mode="before")
    @classmethod
    def _ref_mp(cls, v: object) -> object:
        return _recortar(v)


class ConfirmarVentaRequest(BaseModel):
    """Body de POST /api/ventas/{id}/confirmar: solo pagos (D4)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    pagos: list[PagoVentaIn] = Field(min_length=1, max_length=MAX_PAGOS_VENTA)


class AnularVentaRequest(BaseModel):
    """Body de POST /api/ventas/{id}/anular: motivo obligatorio (D13)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    motivo: str = Field(min_length=1, max_length=300)

    @field_validator("motivo", mode="before")
    @classmethod
    def _motivo(cls, v: object) -> object:
        return _recortar(v)


class VentaFiltros(BaseModel):
    """Query de GET /api/ventas (D15).

    No es strict: llega como query string. desde/hasta exigen zona horaria
    (naive => 422): el cliente calcula los bordes del dia local y el
    servidor no asume zona. Intervalo [desde, hasta) sobre created_at.
    """

    estado: ESTADO_VENTA_LITERAL | None = None
    cliente_id: str | None = Field(default=None, min_length=1)
    usuario_id: str | None = Field(default=None, min_length=1)
    desde: AwareDatetime | None = None
    hasta: AwareDatetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class LineaVentaResponse(BaseModel):
    """Linea de venta con su precio congelado; nombre resuelto por join (D15)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    producto_id: str = Field(min_length=1)
    producto_nombre: str
    cantidad: int
    precio_unit: Decimal
    subtotal: Decimal

    @field_serializer("precio_unit", "subtotal")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class PagoVentaResponse(BaseModel):
    """Pago registrado de una venta confirmada."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    metodo: METODO_PAGO_VENTA_LITERAL
    monto: Decimal
    ref_mp: str | None
    created_at: datetime

    @field_serializer("monto")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class VentaResponse(BaseModel):
    """Detalle de venta: lineas, pagos y auditoria de confirmacion/anulacion."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    estado: ESTADO_VENTA_LITERAL
    cliente_id: str | None
    usuario_id: str = Field(min_length=1)
    total: Decimal
    lineas: list[LineaVentaResponse] = Field(default_factory=list)
    pagos: list[PagoVentaResponse] = Field(default_factory=list)
    created_at: datetime
    confirmada_at: datetime | None
    confirmada_por_id: str | None
    anulada_at: datetime | None
    anulada_por_id: str | None
    motivo_anulacion: str | None

    @field_serializer("total")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class VentaResumen(BaseModel):
    """Venta sin lineas ni pagos, para listados e historial por cliente."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    estado: ESTADO_VENTA_LITERAL
    cliente_id: str | None
    usuario_id: str = Field(min_length=1)
    total: Decimal
    created_at: datetime
    confirmada_at: datetime | None
    anulada_at: datetime | None

    @field_serializer("total")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


class VentaListResponse(PaginacionResponse):
    """Envelope paginado de GET /api/ventas y /api/clientes/{id}/ventas."""

    items: list[VentaResumen] = Field(default_factory=list)
