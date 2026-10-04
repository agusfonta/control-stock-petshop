"""Stock router: lectura con badge de bajo minimo (C-05, RN-ST-01).

GET /api/stock: productos activos con bajo_minimo derivado
(stock_actual <= stock_minimo, decision D3), filtro bajo_minimo=true
y orden=rotacion (cobertura ascendente, decision D4). Requiere auth.
GET /api/stock/alertas: resumen de reposicion con fallback a DB
si Redis cae (llega en task 4.2).
"""

import math
from typing import Literal

import redis as redis_lib
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import deps
from app.models import Producto
from app.schemas import AlertasResponse, StockItem, StockListResponse
from app.workers.stock_alerts import ids_bajo_minimo

router = APIRouter(prefix="/stock", tags=["stock"])

MAX_PAGE_SIZE = 100


def _to_stock_item(producto: Producto) -> StockItem:
    """Serializa el ORM a StockItem con el badge derivado (D3)."""
    return StockItem(
        id=producto.id,
        sku=producto.sku,
        nombre=producto.nombre,
        marca=producto.marca,
        categoria=producto.categoria,
        unidad=str(producto.unidad),
        costo=producto.costo,
        margen_pct=producto.margen_pct,
        precio_venta=producto.precio_venta,
        stock_actual=producto.stock_actual,
        stock_minimo=producto.stock_minimo,
        bajo_minimo=producto.stock_actual <= producto.stock_minimo,
        distribuidora_default_id=producto.distribuidora_default_id,
        activo=producto.activo,
        created_at=producto.created_at,
        updated_at=producto.updated_at,
    )


@router.get("", response_model=StockListResponse)
def listar_stock(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    bajo_minimo: bool | None = Query(default=None),
    orden: Literal["rotacion"] | None = Query(default=None),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> StockListResponse:
    """Lista paginada de stock con badge y filtros de reposicion."""
    _ = current
    query = db.query(Producto).filter(Producto.activo.is_(True))
    if bajo_minimo is True:
        query = query.filter(Producto.stock_actual <= Producto.stock_minimo)
    if orden == "rotacion":
        query = query.order_by(
            (Producto.stock_actual - Producto.stock_minimo).asc(),
            Producto.id.asc(),
        )
    else:
        query = query.order_by(Producto.created_at, Producto.id)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = math.ceil(total / page_size) if total else 0
    return StockListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_stock_item(p) for p in items],
    )


@router.get("/alertas", response_model=AlertasResponse)
def resumen_alertas(
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
    cache: redis_lib.Redis = Depends(deps.get_redis),
) -> AlertasResponse:
    """Resumen de reposicion: total bajo minimo + items (Flujo 2).

    Lee el SET del job si esta disponible; ante Redis caido o SET
    vacio/ausente degrada a computo directo sin responder 500. Los ids
    del cache se recargan desde la base y se re-filtran (stale-guard:
    un producto repuesto entre jobs no aparece como alerta).
    """
    _ = current
    ids: list[str] | None = None
    try:
        cached = cache.smembers("stock:bajo_minimo")
        if cached:
            ids = [str(i) for i in cached]
    except redis_lib.exceptions.RedisError:
        ids = None
    if ids is None:
        ids = ids_bajo_minimo(db)
    if ids:
        candidatos = (
            db.query(Producto)
            .filter(Producto.activo.is_(True), Producto.id.in_(ids))
            .all()
        )
    else:
        candidatos = []
    items = sorted(
        (p for p in candidatos if p.stock_actual <= p.stock_minimo),
        key=lambda p: (p.stock_actual - p.stock_minimo, p.id),
    )
    return AlertasResponse(
        total_bajo_minimo=len(items),
        items=[_to_stock_item(p) for p in items],
    )
