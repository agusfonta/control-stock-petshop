"""Ventas router: borrador, confirmar, anular y lecturas (C-10, D12/D16).

Router delgado: valida con schemas estrictos, delega en services.ventas y
mapea sus errores de dominio a HTTP (NoEncontrado 404, ReferenciaInactiva/
IdempotenciaConflicto/PagosInvalidos 422, StockInsuficiente/EstadoInvalido/
RefMpDuplicada 409). Escrituras con require_role("duena", "mostrador")
explicito; anular solo duena. Rutas fijas antes que las parametrizadas.
"""

import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import deps
from app.models import Venta
from app.schemas import (
    AnularVentaRequest,
    ConfirmarVentaRequest,
    LineaVentaResponse,
    PagoVentaResponse,
    VentaCreate,
    VentaFiltros,
    VentaListResponse,
    VentaResponse,
    VentaResumen,
)
from app.services import ventas as svc

router = APIRouter(prefix="/ventas", tags=["ventas"])

# Mapeo error de dominio -> HTTP (clases hermanas: lookup exacto por tipo).
_HTTP_POR_ERROR: dict[type[svc.VentasError], int] = {
    svc.NoEncontrado: status.HTTP_404_NOT_FOUND,
    svc.ReferenciaInactiva: status.HTTP_422_UNPROCESSABLE_ENTITY,
    svc.IdempotenciaConflicto: status.HTTP_422_UNPROCESSABLE_ENTITY,
    svc.PagosInvalidos: status.HTTP_422_UNPROCESSABLE_ENTITY,
    svc.StockInsuficiente: status.HTTP_409_CONFLICT,
    svc.EstadoInvalido: status.HTTP_409_CONFLICT,
    svc.RefMpDuplicada: status.HTTP_409_CONFLICT,
}


def _http_error(exc: svc.VentasError) -> HTTPException:
    """Traduce un error de dominio a su HTTPException."""
    codigo = _HTTP_POR_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, svc.StockInsuficiente):
        # D7: el POS necesita los faltantes para sugerir la cantidad disponible.
        detail: object = {"mensaje": str(exc), "faltantes": exc.faltantes}
    else:
        detail = str(exc)
    return HTTPException(status_code=codigo, detail=detail)


def _to_venta_response(venta: Venta) -> VentaResponse:
    """Serializa la venta con lineas (nombre por join) y pagos."""
    return VentaResponse(
        id=venta.id,
        estado=str(venta.estado),
        cliente_id=venta.cliente_id,
        usuario_id=venta.usuario_id,
        total=venta.total,
        lineas=[
            LineaVentaResponse(
                id=linea.id,
                producto_id=linea.producto_id,
                producto_nombre=linea.producto.nombre,
                cantidad=linea.cantidad,
                precio_unit=linea.precio_unit,
                subtotal=linea.subtotal,
            )
            for linea in venta.lineas
        ],
        pagos=[
            PagoVentaResponse(
                id=pago.id,
                metodo=str(pago.metodo),
                monto=pago.monto,
                ref_mp=pago.ref_mp,
                created_at=pago.created_at,
            )
            for pago in venta.pagos
        ],
        created_at=venta.created_at,
        confirmada_at=venta.confirmada_at,
        confirmada_por_id=venta.confirmada_por_id,
        anulada_at=venta.anulada_at,
        anulada_por_id=venta.anulada_por_id,
        motivo_anulacion=venta.motivo_anulacion,
    )


@router.post("", response_model=VentaResponse, status_code=201)
def crear_venta(
    data: VentaCreate,
    response: Response,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_role("duena", "mostrador")),
) -> VentaResponse:
    """Crea un borrador (201) o devuelve el existente por idempotencia (200)."""
    try:
        venta, creada = svc.crear_venta(db, data, current)
    except svc.VentasError as exc:
        raise _http_error(exc) from None
    if not creada:
        response.status_code = status.HTTP_200_OK
    return _to_venta_response(venta)


def _to_venta_resumen(venta: Venta) -> VentaResumen:
    """Serializa la venta sin lineas ni pagos (listados e historial)."""
    return VentaResumen(
        id=venta.id,
        estado=str(venta.estado),
        cliente_id=venta.cliente_id,
        usuario_id=venta.usuario_id,
        total=venta.total,
        created_at=venta.created_at,
        confirmada_at=venta.confirmada_at,
        anulada_at=venta.anulada_at,
    )


def to_venta_list_response(
    items: list[Venta], total: int, page: int, page_size: int
) -> VentaListResponse:
    """Envelope paginado de resumenes (lo reutiliza el historial por cliente)."""
    return VentaListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
        items=[_to_venta_resumen(v) for v in items],
    )


@router.get("", response_model=VentaListResponse)
def listar_ventas(
    filtros: Annotated[VentaFiltros, Query()],
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> VentaListResponse:
    """Lista paginada con propiedad: el mostrador solo ve sus ventas."""
    items, total = svc.listar_ventas(db, filtros, current)
    return to_venta_list_response(items, total, filtros.page, filtros.page_size)


@router.get("/{venta_id}", response_model=VentaResponse)
def obtener_venta(
    venta_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> VentaResponse:
    """Detalle de la venta con lineas y pagos (ajena => 404 para mostrador)."""
    try:
        venta = svc.obtener_venta(db, venta_id, current)
    except svc.VentasError as exc:
        raise _http_error(exc) from None
    return _to_venta_response(venta)


@router.post("/{venta_id}/confirmar", response_model=VentaResponse)
def confirmar_venta(
    venta_id: str,
    data: ConfirmarVentaRequest,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_role("duena", "mostrador")),
) -> VentaResponse:
    """Confirma el borrador: stock + movimientos + pagos + evento, todo o nada."""
    try:
        venta = svc.confirmar_venta(db, venta_id, data, current)
    except svc.VentasError as exc:
        raise _http_error(exc) from None
    return _to_venta_response(venta)


@router.post("/{venta_id}/anular", response_model=VentaResponse)
def anular_venta(
    venta_id: str,
    data: AnularVentaRequest,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> VentaResponse:
    """Anula una venta confirmada devolviendo el stock (solo duena)."""
    try:
        venta = svc.anular_venta(db, venta_id, data, current)
    except svc.VentasError as exc:
        raise _http_error(exc) from None
    return _to_venta_response(venta)
