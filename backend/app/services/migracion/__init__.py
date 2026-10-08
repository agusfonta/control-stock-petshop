"""Importacion de catalogo desde Excel/CSV (C-08).

`importar()` es el unico nucleo que usan el CLI y el endpoint: lee, resuelve
columnas, analiza (dry-run) y, solo con `confirmar=True` y sin errores,
aplica todo en una transaccion.
"""

import uuid

from sqlalchemy.orm import Session

from app.models import Usuario
from app.schemas import (
    ColumnasReporte,
    FilaReporte,
    MotivoReporte,
    ReporteImportacion,
)
from app.services.migracion.analisis import Plan, analizar
from app.services.migracion.aplicar import CatalogoCambio
from app.services.migracion.aplicar import aplicar as aplicar_plan
from app.services.migracion.columnas import ResultadoColumnas, resolver_columnas
from app.services.migracion.lectura import ArchivoNoAdmitido, Planilla, leer_planilla

__all__ = [
    "ArchivoDemasiadoGrande",
    "ArchivoNoAdmitido",
    "CatalogoCambio",
    "MAX_BYTES",
    "importar",
]

MAX_BYTES = 5 * 1024 * 1024


class ArchivoDemasiadoGrande(Exception):
    """El archivo supera MAX_BYTES (se traduce a 413)."""


def _columnas(planilla: Planilla, resultado: ResultadoColumnas) -> ColumnasReporte:
    return ColumnasReporte(
        mapeadas={
            campo: str(planilla.encabezados[pos]).strip()
            for campo, pos in resultado.indices.items()
        },
        ignoradas=list(resultado.ignoradas),
    )


def _filas(plan: Plan) -> list[FilaReporte]:
    return [
        FilaReporte(
            fila=f.fila,
            sku=f.sku,
            estado=f.estado,
            accion=f.accion,
            motivos=[MotivoReporte(campo=m.campo, mensaje=m.mensaje, gravedad=m.gravedad)
                     for m in f.motivos],
            campos_cambiados=list(f.campos_cambiados),
        )
        for f in plan.filas
    ]


def importar(
    db: Session,
    contenido: bytes,
    nombre_archivo: str,
    usuario: Usuario,
    *,
    confirmar: bool = False,
    mapeo: dict[str, str] | None = None,
    hoja: str | None = None,
) -> ReporteImportacion:
    """Analiza la planilla y, si `confirmar` y no hay errores, la aplica."""
    if len(contenido) > MAX_BYTES:
        raise ArchivoDemasiadoGrande(f"el archivo supera {MAX_BYTES // (1024 * 1024)} MB")
    planilla = leer_planilla(contenido, nombre_archivo, hoja)
    columnas = (
        ResultadoColumnas()
        if planilla.errores
        else resolver_columnas(list(planilla.encabezados), mapeo)
    )
    plan = analizar(db, planilla, columnas)
    lote_id = None
    if confirmar and not plan.hay_errores:
        lote_id = str(uuid.uuid4())
        aplicar_plan(db, plan, usuario, nombre_archivo, lote_id)
    return ReporteImportacion(
        archivo=nombre_archivo,
        confirmado=lote_id is not None,
        lote_id=lote_id,
        errores_globales=list(plan.errores_globales),
        columnas=_columnas(planilla, columnas),
        totales=plan.totales,
        distribuidoras_a_crear=list(plan.distribuidoras_a_crear),
        filas=_filas(plan),
    )
