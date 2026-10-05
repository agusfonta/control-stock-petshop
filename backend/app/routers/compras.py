"""Compras router: pedidos, recepcion, pagos y cuenta (C-07, D4/D8/D12).

Router delgado: valida con schemas estrictos, delega en services.compras
y mapea sus errores de dominio a HTTP (NoEncontrado 404, ReferenciaInactiva
422, EstadoInvalido 409). Pedidos: crear/recibir duena + mostrador, leer
cualquier usuario activo, cancelar solo duena. Pagos y cuenta solo duena.
Rutas fijas declaradas antes que las parametrizadas (D12).
"""

import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app import deps
from app.models import PagoDistribuidora, PedidoCompra
from app.schemas import (
    CuentaDistribuidoraResponse,
    EntradaStockResponse,
    LineaPedidoResponse,
    PagoCreate,
    PagoListResponse,
    PagoResponse,
    PedidoCreate,
    PedidoListResponse,
    PedidoResponse,
)
from app.services import compras as svc

router = APIRouter(prefix="/compras", tags=["compras"])

MAX_PAGE_SIZE = 100

# Mapeo error de dominio -> HTTP (clases hermanas: lookup exacto por tipo).
_HTTP_POR_ERROR: dict[type[svc.ComprasError], int] = {
    svc.NoEncontrado: status.HTTP_404_NOT_FOUND,
    svc.ReferenciaInactiva: status.HTTP_422_UNPROCESSABLE_ENTITY,
    svc.EstadoInvalido: status.HTTP_409_CONFLICT,
}


def _http_error(exc: svc.ComprasError) -> HTTPException:
    """Traduce un error de dominio a su HTTPException."""
    codigo = _HTTP_POR_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=codigo, detail=str(exc))


def _to_pedido_response(pedido: PedidoCompra) -> PedidoResponse:
    """Serializa el pedido con subtotales por linea y total estimado."""
    return PedidoResponse(
        id=pedido.id,
        distribuidora_id=pedido.distribuidora_id,
        estado=str(pedido.estado),
        usuario_id=pedido.usuario_id,
        notas=pedido.notas,
        recibido_at=pedido.recibido_at,
        recibido_por_id=pedido.recibido_por_id,
        total_estimado=svc.total_pedido(pedido),
        lineas=[
            LineaPedidoResponse(
                id=linea.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                costo_unitario=linea.costo_unitario,
                subtotal=linea.cantidad * linea.costo_unitario,
            )
            for linea in pedido.lineas
        ],
        entradas=[
            EntradaStockResponse(
                id=entrada.id,
                producto_id=entrada.producto_id,
                cantidad=entrada.cantidad,
                costo_unitario=entrada.costo_unitario,
                usuario_id=entrada.usuario_id,
                created_at=entrada.created_at,
            )
            for entrada in pedido.entradas
        ],
        created_at=pedido.created_at,
        updated_at=pedido.updated_at,
    )


def _to_pago_response(pago: PagoDistribuidora) -> PagoResponse:
    """Serializa el pago a PagoResponse."""
    return PagoResponse(
        id=pago.id,
        distribuidora_id=pago.distribuidora_id,
        monto=pago.monto,
        metodo=str(pago.metodo),
        fecha=pago.fecha,
        nota=pago.nota,
        usuario_id=pago.usuario_id,
        activo=pago.activo,
        created_at=pago.created_at,
        updated_at=pago.updated_at,
    )


@router.post("/pedidos", response_model=PedidoResponse, status_code=201)
def crear_pedido(
    data: PedidoCreate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_role("duena", "mostrador")),
) -> PedidoResponse:
    """Crea un pedido pendiente sin mover stock (duena y mostrador)."""
    try:
        pedido = svc.crear_pedido(db, data, current)
    except svc.ComprasError as exc:
        raise _http_error(exc) from None
    return _to_pedido_response(pedido)


@router.get("/pedidos", response_model=PedidoListResponse)
def listar_pedidos(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    estado: Literal["pendiente", "recibido", "cancelado"] | None = Query(
        default=None
    ),
    distribuidora_id: str | None = Query(default=None, min_length=1),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> PedidoListResponse:
    """Lista paginada de pedidos, filtrable por estado y distribuidora."""
    _ = current
    query = db.query(PedidoCompra)
    if estado is not None:
        query = query.filter(PedidoCompra.estado == estado)
    if distribuidora_id is not None:
        query = query.filter(PedidoCompra.distribuidora_id == distribuidora_id)
    total = query.count()
    items = (
        query.options(
            selectinload(PedidoCompra.lineas), selectinload(PedidoCompra.entradas)
        )
        .order_by(PedidoCompra.created_at.desc(), PedidoCompra.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0
    return PedidoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_pedido_response(p) for p in items],
    )


@router.get("/pedidos/{pedido_id}", response_model=PedidoResponse)
def obtener_pedido(
    pedido_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> PedidoResponse:
    """Detalle del pedido con lineas, total estimado y entradas."""
    _ = current
    try:
        pedido = svc.obtener_pedido(db, pedido_id)
    except svc.ComprasError as exc:
        raise _http_error(exc) from None
    return _to_pedido_response(pedido)


@router.post("/pedidos/{pedido_id}/recibir", response_model=PedidoResponse)
def recibir_pedido(
    pedido_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_role("duena", "mostrador")),
) -> PedidoResponse:
    """Recibe el pedido completo: stock + entradas + costos, todo o nada."""
    try:
        pedido = svc.recibir_pedido(db, pedido_id, current)
    except svc.ComprasError as exc:
        raise _http_error(exc) from None
    return _to_pedido_response(pedido)


@router.post("/pedidos/{pedido_id}/cancelar", response_model=PedidoResponse)
def cancelar_pedido(
    pedido_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> PedidoResponse:
    """Cancela un pedido pendiente (solo duena); no mueve stock."""
    _ = current
    try:
        pedido = svc.cancelar_pedido(db, pedido_id)
    except svc.ComprasError as exc:
        raise _http_error(exc) from None
    return _to_pedido_response(pedido)


@router.post("/pagos", response_model=PagoResponse, status_code=201)
def registrar_pago(
    data: PagoCreate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> PagoResponse:
    """Registra un pago a una distribuidora (solo duena, sin pedido asociado)."""
    try:
        pago = svc.registrar_pago(db, data, current)
    except svc.ComprasError as exc:
        raise _http_error(exc) from None
    return _to_pago_response(pago)


@router.get("/pagos", response_model=PagoListResponse)
def listar_pagos(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    distribuidora_id: str | None = Query(default=None, min_length=1),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> PagoListResponse:
    """Lista paginada de pagos activos (solo duena); los anulados no aparecen."""
    _ = current
    query = db.query(PagoDistribuidora).filter(PagoDistribuidora.activo.is_(True))
    if distribuidora_id is not None:
        query = query.filter(PagoDistribuidora.distribuidora_id == distribuidora_id)
    total = query.count()
    items = (
        query.order_by(
            PagoDistribuidora.fecha.desc(),
            PagoDistribuidora.created_at.desc(),
            PagoDistribuidora.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0
    return PagoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_pago_response(p) for p in items],
    )


@router.delete("/pagos/{pago_id}", status_code=204)
def anular_pago(
    pago_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Anula un pago (soft-delete, solo duena)."""
    _ = current
    try:
        svc.anular_pago(db, pago_id)
    except svc.ComprasError as exc:
        raise _http_error(exc) from None


@router.get(
    "/distribuidoras/{distribuidora_id}/cuenta",
    response_model=CuentaDistribuidoraResponse,
)
def cuenta_distribuidora(
    distribuidora_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> CuentaDistribuidoraResponse:
    """Cuenta simple: recibido - pagado = saldo (solo duena, al vuelo)."""
    _ = current
    try:
        recibido, pagado, saldo = svc.cuenta_distribuidora(db, distribuidora_id)
    except svc.ComprasError as exc:
        raise _http_error(exc) from None
    return CuentaDistribuidoraResponse(
        distribuidora_id=distribuidora_id,
        total_recibido=recibido,
        total_pagado=pagado,
        saldo=saldo,
    )
