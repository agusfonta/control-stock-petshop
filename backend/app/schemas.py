"""Pydantic schemas (strict). C-01: solo HealthResponse."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.texto import normalizar_telefono


class HealthResponse(BaseModel):
    """Respuesta de GET /api/health."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: str = Field(pattern=r"^ok$")
    version: str = Field(min_length=1)


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    """Credenciales de POST /api/auth/login (password sin longitud minima
    para que una clave corta y erronea sea 401, no 422)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    """Par de acceso: el access viaja en body, el refresh en cookie."""

    model_config = ConfigDict(extra="forbid", strict=True)

    access_token: str = Field(min_length=1)
    token_type: str = Field(pattern=r"^bearer$")


class MeResponse(BaseModel):
    """Identidad del usuario actual (GET /api/auth/me)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    email: str = Field(pattern=EMAIL_PATTERN)
    rol: str = Field(min_length=1)
    activo: bool


class CrearUsuarioRequest(BaseModel):
    """Alta de usuario, solo duena (POST /api/usuarios)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    rol: Literal["duena", "mostrador"]


class UsuarioResponse(BaseModel):
    """Usuario creado/devuelto (jamas incluye password ni hash)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    email: str = Field(pattern=EMAIL_PATTERN)
    rol: str = Field(min_length=1)
    activo: bool


# --- C-04: catalogo de productos ---

SKU_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
UNIDAD_LITERAL = Literal["unidad", "bolsa", "caja"]


def _coerce_decimal(v: object) -> object:
    """Convierte int/float/str de JSON a Decimal antes del check estricto.

    Con strict=True, Pydantic v2 solo acepta instancias Decimal; los numeros
    JSON llegan como int/float. Este before-validator los normaliza. bool se
    deja pasar para que el check estricto lo rechace (bool no es numero).
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float, str)):
        try:
            return Decimal(str(v))
        except InvalidOperation:
            # InvalidOperation no es ValueError: sin esto un "abc" daria 500
            # en vez de 422.
            raise ValueError("no es un numero valido") from None
    return v


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
        return _coerce_decimal(v)


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
        return _coerce_decimal(v)


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


class ListaPrecioCreate(BaseModel):
    """Alta de costo por distribuidora (persistencia C-04, sin logica)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    distribuidora_id: str = Field(min_length=1)
    producto_id: str = Field(min_length=1)
    costo: Decimal = Field(gt=0)

    @field_validator("costo", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return _coerce_decimal(v)


class MargenMinimoRequest(BaseModel):
    """PATCH /api/productos/{id}/margen-minimo (solo duena)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    margen_pct: Decimal | None = Field(default=None, ge=0)
    stock_minimo: int | None = Field(default=None, ge=0)

    @field_validator("margen_pct", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return _coerce_decimal(v)


class PaginacionResponse(BaseModel):
    """Metadata de paginado offset-based (D5)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class BusquedaResponse(PaginacionResponse):
    """Envelope de listado/busqueda: items + metadata de paginacion."""

    items: list[ProductoResponse] = Field(default_factory=list)


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


# --- C-06: distribuidoras y listas de precios ---


def _nombre_no_vacio(v: object) -> object:
    """Rechaza strings en blanco (solo espacios) antes del check de longitud."""
    if isinstance(v, str) and not v.strip():
        raise ValueError("nombre no puede estar vacio")
    return v


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
        return _nombre_no_vacio(v)


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
        return _nombre_no_vacio(v)


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
        return _coerce_decimal(v)


class ListaPrecioUpdate(BaseModel):
    """Actualizacion del costo de una entrada (PUT .../listas/{producto_id})."""

    model_config = ConfigDict(extra="forbid", strict=True)

    costo: Decimal = Field(gt=0)

    @field_validator("costo", mode="before")
    @classmethod
    def _dec(cls, v: object) -> object:
        return _coerce_decimal(v)


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


def _serialize_money(v: Decimal) -> int | float:
    """Decimal como numero JSON (int si no hay decimales), como en C-04."""
    if v == v.to_integral_value():
        return int(v)
    return float(v)


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
        return _serialize_money(v)


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
        return _serialize_money(v)


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
        return _serialize_money(v)


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
        return _coerce_decimal(v)

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
        return _serialize_money(v)


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
        return _serialize_money(v)


# --- C-09: clientes (saldo_cc reservado: no se acepta ni se expone, D8) ---


def _opcional_en_blanco(v: object) -> object:
    """Recorta strings opcionales; en blanco -> None (se guarda como nulo)."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _nombre_cliente(v: object) -> object:
    """Nombre obligatorio: no nulo, recortado y no vacio."""
    if v is None:
        raise ValueError("nombre no puede ser nulo")
    if isinstance(v, str):
        v = v.strip()
    return _nombre_no_vacio(v)


def _email_cliente(v: object) -> object:
    """Email opcional: recortado, en minusculas; en blanco -> None."""
    v = _opcional_en_blanco(v)
    return v.lower() if isinstance(v, str) else v


def _telefono_cliente(v: object) -> object:
    """Telefono opcional: normalizado a digitos (con + inicial opcional)."""
    v = _opcional_en_blanco(v)
    return normalizar_telefono(v) if isinstance(v, str) else v


class ClienteCreate(BaseModel):
    """Alta de cliente (POST /api/clientes): solo `nombre` es obligatorio."""

    model_config = ConfigDict(extra="forbid", strict=True)

    nombre: str = Field(min_length=1, max_length=200)
    telefono: str | None = Field(default=None, max_length=21)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL_PATTERN)
    direccion: str | None = Field(default=None, max_length=300)

    @field_validator("nombre", mode="before")
    @classmethod
    def _nombre(cls, v: object) -> object:
        return _nombre_cliente(v)

    @field_validator("telefono", mode="before")
    @classmethod
    def _telefono(cls, v: object) -> object:
        return _telefono_cliente(v)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v: object) -> object:
        return _email_cliente(v)

    @field_validator("direccion", mode="before")
    @classmethod
    def _direccion(cls, v: object) -> object:
        return _opcional_en_blanco(v)


class ClienteUpdate(BaseModel):
    """Actualizacion parcial (PUT /api/clientes/{id}); `nombre` no puede ser nulo."""

    model_config = ConfigDict(extra="forbid", strict=True)

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    telefono: str | None = Field(default=None, max_length=21)
    email: str | None = Field(default=None, max_length=320, pattern=EMAIL_PATTERN)
    direccion: str | None = Field(default=None, max_length=300)

    @field_validator("nombre", mode="before")
    @classmethod
    def _nombre(cls, v: object) -> object:
        return _nombre_cliente(v)

    @field_validator("telefono", mode="before")
    @classmethod
    def _telefono(cls, v: object) -> object:
        return _telefono_cliente(v)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v: object) -> object:
        return _email_cliente(v)

    @field_validator("direccion", mode="before")
    @classmethod
    def _direccion(cls, v: object) -> object:
        return _opcional_en_blanco(v)


class ClienteResponse(BaseModel):
    """Cliente expuesto via API (sin `saldo_cc`, reservado en v1)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    nombre: str
    telefono: str | None
    email: str | None
    direccion: str | None
    activo: bool
    created_at: datetime
    updated_at: datetime


class ClienteListResponse(PaginacionResponse):
    """Envelope paginado de GET /api/clientes y /api/clientes/buscar."""

    items: list[ClienteResponse] = Field(default_factory=list)


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
        return _coerce_decimal(v)

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
        return _serialize_money(v)


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
        return _serialize_money(v)


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
        return _serialize_money(v)


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
        return _serialize_money(v)


class VentaListResponse(PaginacionResponse):
    """Envelope paginado de GET /api/ventas y /api/clientes/{id}/ventas."""

    items: list[VentaResumen] = Field(default_factory=list)


# --- C-14: reportes de solo lectura (D6, D13) ---

# Dinero a centavos y porcentaje con 4 decimales: el servicio redondea, el
# schema lo exige para que nunca salga un importe con decimales de mas.
Dinero = Annotated[Decimal, Field(decimal_places=2)]
Porcentaje = Annotated[Decimal, Field(decimal_places=4)]

_FECHA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _fecha_iso(v: object) -> object:
    """Solo `YYYY-MM-DD` (D6): rechaza horas y otros formatos que date acepta.

    El modo laxo de Pydantic admitiria '2026-10-06T00:00:00' o '20261006';
    la spec los manda a 422.
    """
    if isinstance(v, str):
        if not _FECHA_ISO.match(v):
            raise ValueError("fecha invalida: se espera YYYY-MM-DD")
        return date.fromisoformat(v)
    if isinstance(v, datetime):
        raise ValueError("fecha invalida: se espera YYYY-MM-DD")
    return v


class VentasDiaQuery(BaseModel):
    """Query de GET /api/reportes/ventas-dia: un dia local, default hoy (D6)."""

    model_config = ConfigDict(extra="forbid")

    fecha: date | None = None

    _fecha_iso = field_validator("fecha", mode="before")(_fecha_iso)

    @model_validator(mode="after")
    def _fecha_por_defecto(self) -> "VentasDiaQuery":
        # Import diferido: services.reportes importa este modulo.
        from app.services.reportes import hoy

        if self.fecha is None:
            self.fecha = hoy()
        return self


class PeriodoQuery(BaseModel):
    """Periodo desde/hasta (ambos inclusive) con defaults y limites de D6.

    Tras validar, `desde` y `hasta` son siempre fechas: los defaults ya
    estan resueltos y un periodo invertido o de mas de 366 dias es 422.
    """

    model_config = ConfigDict(extra="forbid")

    desde: date | None = None
    hasta: date | None = None

    _fecha_iso = field_validator("desde", "hasta", mode="before")(_fecha_iso)

    @model_validator(mode="after")
    def _resolver_periodo(self) -> "PeriodoQuery":
        # Import diferido: services.reportes importa este modulo.
        from app.services.reportes import resolver_periodo

        self.desde, self.hasta = resolver_periodo(self.desde, self.hasta)
        return self


class MasVendidosQuery(PeriodoQuery):
    """Query de GET /api/reportes/mas-vendidos (D8): top-N sin paginar."""

    orden: Literal["cantidad", "monto"] = "cantidad"
    limite: int = Field(default=10, ge=1, le=50)


class ReposicionQuery(BaseModel):
    """Query de GET /api/reportes/reposicion (D9)."""

    model_config = ConfigDict(extra="forbid")

    dias: int = Field(default=30, ge=7, le=180)
    cobertura_max_dias: int = Field(default=7, ge=1, le=90)


class MargenesQuery(PeriodoQuery):
    """Query de GET /api/reportes/margenes (D10): paginado 20/100."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class _ReporteResponse(BaseModel):
    """Base de las respuestas de reportes: estrictas, sin campos extra."""

    model_config = ConfigDict(extra="forbid", strict=True)


class MetodoTotal(_ReporteResponse):
    """Monto y cantidad de pagos de un metodo en el dia."""

    metodo: METODO_PAGO_VENTA_LITERAL
    monto: Dinero
    cantidad_pagos: int = Field(ge=0)

    @field_serializer("monto")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return _serialize_money(v)


class AnuladasResumen(_ReporteResponse):
    """Ventas confirmadas el dia que hoy estan anuladas (D4), aparte."""

    cantidad: int = Field(ge=0)
    total: Dinero

    @field_serializer("total")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return _serialize_money(v)


class VentasDiaResponse(_ReporteResponse):
    """Ventas del dia local (D7); `alcance` dice si son todas o las propias."""

    fecha: date
    alcance: Literal["todas", "propias"]
    cantidad_ventas: int = Field(ge=0)
    total_vendido: Dinero
    ticket_promedio: Dinero
    unidades_vendidas: int = Field(ge=0)
    por_metodo: list[MetodoTotal]
    anuladas: AnuladasResumen

    @field_serializer("total_vendido", "ticket_promedio")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return _serialize_money(v)


class ProductoVendido(_ReporteResponse):
    """Fila del ranking de mas vendidos (incluye productos dados de baja)."""

    producto_id: str = Field(min_length=1)
    sku: str
    nombre: str
    activo: bool
    unidades: int = Field(ge=0)
    monto: Dinero

    @field_serializer("monto")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return _serialize_money(v)


class MasVendidosResponse(_ReporteResponse):
    """Ranking de a lo sumo `limite` productos del periodo (D8)."""

    desde: date
    hasta: date
    orden: Literal["cantidad", "monto"]
    items: list[ProductoVendido]


class ReposicionItem(_ReporteResponse):
    """Producto a reponer: sin costos, precios ni importes (lo ve el mostrador)."""

    producto_id: str = Field(min_length=1)
    sku: str
    nombre: str
    stock_actual: int
    stock_minimo: int
    bajo_minimo: bool
    unidades_vendidas: int = Field(ge=0)
    venta_diaria: Dinero
    cobertura_dias: int | None = Field(ge=0)
    distribuidora_default_id: str | None

    @field_serializer("venta_diaria")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return _serialize_money(v)


class ReposicionResponse(_ReporteResponse):
    """Reposicion por minimo y rotacion (D9)."""

    dias: int
    cobertura_max_dias: int
    items: list[ReposicionItem]


class MargenProducto(_ReporteResponse):
    """Margen de un producto sobre las lineas con costo congelado (D10)."""

    producto_id: str = Field(min_length=1)
    sku: str
    nombre: str
    unidades: int = Field(ge=0)
    ingresos: Dinero
    costo: Dinero
    margen_bruto: Dinero
    margen_pct: Porcentaje | None

    @field_serializer("ingresos", "costo", "margen_bruto", "margen_pct")
    def _serialize_decimal(self, v: Decimal | None) -> int | float | None:
        return None if v is None else _serialize_money(v)


class MargenesTotales(_ReporteResponse):
    """Totales de todo el periodo (no de la pagina) y lineas sin costo (D1/D10)."""

    ingresos: Dinero
    costo: Dinero
    margen_bruto: Dinero
    margen_pct: Porcentaje | None
    lineas_sin_costo: int = Field(ge=0)
    ingresos_sin_costo: Dinero

    @field_serializer(
        "ingresos", "costo", "margen_bruto", "margen_pct", "ingresos_sin_costo"
    )
    def _serialize_decimal(self, v: Decimal | None) -> int | float | None:
        return None if v is None else _serialize_money(v)


class MargenesResponse(PaginacionResponse):
    """Margenes por producto paginados + totales del periodo completo."""

    desde: date
    hasta: date
    totales: MargenesTotales
    items: list[MargenProducto]


# --- C-08: migracion de productos desde Excel/CSV ---

CAMPO_MIGRACION_LITERAL = Literal[
    "sku", "nombre", "categoria", "marca", "distribuidora", "costo",
    "margen_pct", "precio_venta", "stock_inicial", "stock_minimo", "unidad",
]
ESTADO_FILA_LITERAL = Literal["ok", "advertencia", "error"]
ACCION_FILA_LITERAL = Literal["crear", "actualizar", "sin_cambios"]
GRAVEDAD_LITERAL = Literal["error", "advertencia"]


class _MigracionModel(BaseModel):
    """Base de los modelos de migracion: estrictos, sin campos extra."""

    model_config = ConfigDict(extra="forbid", strict=True)


class MapeoColumnas(_MigracionModel):
    """Mapeo explicito campo canonico -> encabezado de la planilla (gana a los alias)."""

    sku: str | None = None
    nombre: str | None = None
    categoria: str | None = None
    marca: str | None = None
    distribuidora: str | None = None
    costo: str | None = None
    margen_pct: str | None = None
    precio_venta: str | None = None
    stock_inicial: str | None = None
    stock_minimo: str | None = None
    unidad: str | None = None

    @field_validator("*")
    @classmethod
    def _encabezado_no_vacio(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("el encabezado del mapeo no puede estar vacio")
        return v

    def a_dict(self) -> dict[str, str]:
        """Solo los campos presentes: `{campo: encabezado}`."""
        return self.model_dump(exclude_none=True)


class MotivoReporte(_MigracionModel):
    """Un motivo (error o advertencia) de una fila; `campo` es None si es general."""

    campo: str | None
    mensaje: str = Field(min_length=1)
    gravedad: GRAVEDAD_LITERAL


class FilaReporte(_MigracionModel):
    """Resultado del analisis de una fila de datos (numero real del Excel)."""

    fila: int = Field(ge=2)
    sku: str | None
    estado: ESTADO_FILA_LITERAL
    accion: ACCION_FILA_LITERAL | None
    motivos: list[MotivoReporte] = Field(default_factory=list)
    campos_cambiados: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherencia(self) -> "FilaReporte":
        graves = any(m.gravedad == "error" for m in self.motivos)
        avisos = any(m.gravedad == "advertencia" for m in self.motivos)
        esperado = "error" if graves else "advertencia" if avisos else "ok"
        if self.estado != esperado:
            raise ValueError(f"estado {self.estado} no coincide con los motivos ({esperado})")
        if (self.estado == "error") != (self.accion is None):
            raise ValueError("la accion es None si y solo si el estado es error")
        if self.campos_cambiados and self.accion != "actualizar":
            raise ValueError("campos_cambiados solo corresponde a la accion actualizar")
        return self


class TotalesImportacion(_MigracionModel):
    """Conteos del analisis: por estado, por accion y efectos sobre stock/proveedores."""

    filas: int = Field(ge=0)
    ok: int = Field(ge=0)
    advertencias: int = Field(ge=0)
    errores: int = Field(ge=0)
    crear: int = Field(ge=0)
    actualizar: int = Field(ge=0)
    sin_cambios: int = Field(ge=0)
    distribuidoras_a_crear: int = Field(ge=0)
    unidades_apertura: int = Field(ge=0)

    @model_validator(mode="after")
    def _coherencia(self) -> "TotalesImportacion":
        if self.ok + self.advertencias + self.errores != self.filas:
            raise ValueError("ok + advertencias + errores debe sumar las filas")
        if self.crear + self.actualizar + self.sin_cambios != self.filas - self.errores:
            raise ValueError("las acciones deben sumar las filas sin error")
        return self


class ColumnasReporte(_MigracionModel):
    """Que columna alimenta cada campo y cuales se ignoraron."""

    mapeadas: dict[str, str]
    ignoradas: list[str]


class ReporteImportacion(_MigracionModel):
    """Respuesta de POST /api/migracion/productos y salida de `importar()`."""

    archivo: str
    confirmado: bool
    lote_id: str | None = Field(default=None, max_length=36)
    errores_globales: list[str]
    columnas: ColumnasReporte
    totales: TotalesImportacion
    distribuidoras_a_crear: list[str]
    filas: list[FilaReporte]

    @model_validator(mode="after")
    def _coherencia(self) -> "ReporteImportacion":
        if self.confirmado != (self.lote_id is not None):
            raise ValueError("lote_id debe estar si y solo si confirmado es true")
        t = self.totales
        por_estado = {e: sum(f.estado == e for f in self.filas) for e in ("ok", "advertencia", "error")}
        por_accion = {a: sum(f.accion == a for f in self.filas)
                      for a in ("crear", "actualizar", "sin_cambios")}
        if (t.filas, t.ok, t.advertencias, t.errores) != (
            len(self.filas), por_estado["ok"], por_estado["advertencia"], por_estado["error"]
        ):
            raise ValueError("los totales por estado no coinciden con las filas")
        if (t.crear, t.actualizar, t.sin_cambios) != (
            por_accion["crear"], por_accion["actualizar"], por_accion["sin_cambios"]
        ):
            raise ValueError("los totales por accion no coinciden con las filas")
        if t.distribuidoras_a_crear != len(self.distribuidoras_a_crear):
            raise ValueError("distribuidoras_a_crear no coincide con el total")
        if self.confirmado and (self.errores_globales or t.errores):
            raise ValueError("un reporte confirmado no puede tener errores")
        return self
