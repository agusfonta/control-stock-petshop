"""Schemas de reportes (C-14)."""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.schemas import (
    PaginacionResponse,
    serialize_money,
)
from app.modules.ventas.schemas import METODO_PAGO_VENTA_LITERAL

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
        from app.modules.reportes.service import hoy

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
        from app.modules.reportes.service import resolver_periodo

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
        return serialize_money(v)


class AnuladasResumen(_ReporteResponse):
    """Ventas confirmadas el dia que hoy estan anuladas (D4), aparte."""

    cantidad: int = Field(ge=0)
    total: Dinero

    @field_serializer("total")
    def _serialize_decimal(self, v: Decimal) -> int | float:
        return serialize_money(v)


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
        return serialize_money(v)


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
        return serialize_money(v)


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
        return serialize_money(v)


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
        return None if v is None else serialize_money(v)


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
        return None if v is None else serialize_money(v)


class MargenesResponse(PaginacionResponse):
    """Margenes por producto paginados + totales del periodo completo."""

    desde: date
    hasta: date
    totales: MargenesTotales
    items: list[MargenProducto]
