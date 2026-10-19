"""Schemas de migracion de productos (C-08)."""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

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
