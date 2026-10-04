"""Pydantic schemas (strict). C-01: solo HealthResponse."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


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
        return Decimal(str(v))
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
