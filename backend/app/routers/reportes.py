"""Reportes router: ventas del dia, mas vendidos, reposicion y margenes (C-14, D12).

Router delgado y de solo lectura: valida con modelos de query estrictos
(parametros desconocidos, fechas no ISO y periodos invalidos dan 422) y
delega en services.reportes. Las lecturas del mostrador usan
require_role("duena", "mostrador") explicito (un rol futuro no hereda
acceso); las exclusivas de la duena, require_duena. Sin 404: los reportes no
direccionan recursos.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import deps
from app.schemas import (
    MargenesQuery,
    MargenesResponse,
    MasVendidosQuery,
    MasVendidosResponse,
    ReposicionQuery,
    ReposicionResponse,
    VentasDiaQuery,
    VentasDiaResponse,
)
from app.services import reportes as svc

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/ventas-dia", response_model=VentasDiaResponse)
def ventas_dia(
    query: Annotated[VentasDiaQuery, Query()],
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_role("duena", "mostrador")),
) -> VentasDiaResponse:
    """Ventas del dia local; el mostrador ve solo las suyas (alcance=propias)."""
    return svc.ventas_dia(db, query, current)


@router.get("/mas-vendidos", response_model=MasVendidosResponse)
def mas_vendidos(
    query: Annotated[MasVendidosQuery, Query()],
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> MasVendidosResponse:
    """Top-N de productos del periodo por unidades o monto (solo duena)."""
    return svc.mas_vendidos(db, query, current)


@router.get("/reposicion", response_model=ReposicionResponse)
def reposicion(
    query: Annotated[ReposicionQuery, Query()],
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_role("duena", "mostrador")),
) -> ReposicionResponse:
    """Reposicion por minimo y rotacion, sin importes (duena y mostrador)."""
    _ = current
    return svc.reposicion(db, query)


@router.get("/margenes", response_model=MargenesResponse)
def margenes(
    query: Annotated[MargenesQuery, Query()],
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> MargenesResponse:
    """Margenes por producto con costo historico del periodo (solo duena)."""
    _ = current
    return svc.margenes(db, query)
