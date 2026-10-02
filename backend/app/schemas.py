"""Pydantic schemas (strict). C-01: solo HealthResponse."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
