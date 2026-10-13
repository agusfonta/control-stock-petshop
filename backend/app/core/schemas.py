"""Schemas y validadores compartidos entre modulos."""

from decimal import Decimal, InvalidOperation

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def coerce_decimal(v: object) -> object:
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


# --- C-06: distribuidoras y listas de precios ---


def nombre_no_vacio(v: object) -> object:
    """Rechaza strings en blanco (solo espacios) antes del check de longitud."""
    if isinstance(v, str) and not v.strip():
        raise ValueError("nombre no puede estar vacio")
    return v


def serialize_money(v: Decimal) -> int | float:
    """Decimal como numero JSON (int si no hay decimales), como en C-04."""
    if v == v.to_integral_value():
        return int(v)
    return float(v)


class PaginacionResponse(BaseModel):
    """Metadata de paginado offset-based (D5)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
