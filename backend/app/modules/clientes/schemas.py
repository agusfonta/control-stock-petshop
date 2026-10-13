"""Schemas de clientes (C-09)."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.core.schemas import (
    EMAIL_PATTERN,
    PaginacionResponse,
    nombre_no_vacio,
)
from app.core.texto import normalizar_telefono

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
    return nombre_no_vacio(v)


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
