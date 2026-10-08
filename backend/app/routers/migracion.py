"""Migracion router: POST /api/migracion/productos (C-08, D11).

Adaptador delgado sobre `services.migracion.importar`: solo duena, dry-run por
defecto (`confirmar=false`). Traduce las excepciones del servicio a 413/415/409
y una confirmacion bloqueada por errores a 422 con el reporte por fila.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import deps
from app.schemas import MapeoColumnas, ReporteImportacion
from app.services import migracion as svc
from app.services.migracion import ArchivoDemasiadoGrande, ArchivoNoAdmitido, CatalogoCambio, importar

router = APIRouter(prefix="/migracion", tags=["migracion"])


def _parsear_mapeo(crudo: str | None) -> dict[str, str] | None:
    """JSON de `mapeo` validado con MapeoColumnas; invalido -> 422."""
    if crudo is None or not crudo.strip():
        return None
    try:
        return MapeoColumnas.model_validate(json.loads(crudo)).a_dict()
    except (json.JSONDecodeError, ValidationError) as exc:
        detalle = (
            "mapeo no es un JSON valido"
            if isinstance(exc, json.JSONDecodeError)
            else "mapeo invalido: " + "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
            )
        )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detalle) from None


@router.post(
    "/productos",
    response_model=ReporteImportacion,
    responses={
        409: {"description": "El catalogo cambio durante la confirmacion"},
        413: {"description": "Archivo mayor a 5 MB"},
        415: {"description": "Formato no admitido (solo .xlsx o .csv)"},
        422: {"model": ReporteImportacion, "description": "Confirmacion bloqueada por errores"},
    },
)
def importar_productos(
    archivo: Annotated[UploadFile, File()],
    confirmar: Annotated[bool, Form()] = False,
    mapeo: Annotated[str | None, Form()] = None,
    hoja: Annotated[str | None, Form()] = None,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ReporteImportacion | JSONResponse:
    """Analiza (por defecto) o confirma la carga de productos desde .xlsx/.csv."""
    mapeo_dict = _parsear_mapeo(mapeo)
    contenido = archivo.file.read(svc.MAX_BYTES + 1)  # corta sin leer todo un archivo enorme
    try:
        reporte = importar(
            db, contenido, archivo.filename or "", current,
            confirmar=confirmar, mapeo=mapeo_dict, hoja=hoja or None,
        )
    except ArchivoDemasiadoGrande as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from None
    except ArchivoNoAdmitido as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from None
    except CatalogoCambio as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if confirmar and not reporte.confirmado:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=reporte.model_dump(mode="json"),
        )
    return reporte
