"""Productos router: CRUD + listado paginado (C-04).

Escritura (POST/PUT/DELETE) solo duena (D6); lectura cualquier usuario activo.
precio_venta es column_property (D1): se relee tras commit+refresh.
Soft-delete en DELETE (D2): activo=False, nunca borrado fisico.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import deps
from app.models import Producto
from app.schemas import (
    AjusteStockRequest,
    AjusteStockResponse,
    BusquedaResponse,
    MargenMinimoRequest,
    MovimientoResponse,
    ProductoCreate,
    ProductoResponse,
    ProductoUpdate,
)
from app.services.stock import (
    MotivoInvalido,
    ProductoNoEncontrado,
    StockError,
    StockNegativo,
    ajustar as ajustar_stock,
)

router = APIRouter(prefix="/productos", tags=["productos"])

MAX_PAGE_SIZE = 100


def _to_response(producto: Producto) -> ProductoResponse:
    """Serializa el ORM a ProductoResponse (precio_venta ya calculado)."""
    return ProductoResponse(
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
        distribuidora_default_id=producto.distribuidora_default_id,
        activo=producto.activo,
        created_at=producto.created_at,
        updated_at=producto.updated_at,
    )


def _get_or_404(db: Session, producto_id: str) -> Producto:
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="producto no encontrado",
        )
    return producto


@router.post("", response_model=ProductoResponse, status_code=201)
def crear_producto(
    data: ProductoCreate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ProductoResponse:
    """Crea un producto; precio_venta se calcula solo (RN-PR-01)."""
    _ = current
    existente = db.query(Producto).filter_by(sku=data.sku).one_or_none()
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="sku ya registrado",
        )
    producto = Producto(
        sku=data.sku,
        nombre=data.nombre,
        marca=data.marca,
        categoria=data.categoria,
        unidad=data.unidad,
        costo=data.costo,
        margen_pct=data.margen_pct,
        stock_actual=data.stock_actual,
        stock_minimo=data.stock_minimo,
        distribuidora_default_id=data.distribuidora_default_id,
    )
    db.add(producto)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="sku ya registrado",
        ) from None
    db.refresh(producto)
    return _to_response(producto)


@router.get("", response_model=BusquedaResponse)
def listar_productos(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> BusquedaResponse:
    """Lista paginada (D5) de productos activos (D2)."""
    _ = current
    query = db.query(Producto).filter(Producto.activo.is_(True))
    total = query.count()
    items = (
        query.order_by(Producto.created_at, Producto.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0
    return BusquedaResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_response(p) for p in items],
    )


@router.get("/buscar", response_model=BusquedaResponse)
def buscar_productos(
    q: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> BusquedaResponse:
    """Busca por SKU exacto o nombre parcial (D3), paginado (D5).

    OR(sku == q, nombre ILIKE %q%): el ILIKE usa el indice trgm en Postgres
    y es case-insensitive en SQLite (tests).
    """
    _ = current
    query = db.query(Producto).filter(
        Producto.activo.is_(True),
        or_(Producto.sku == q, Producto.nombre.ilike(f"%{q}%")),
    )
    total = query.count()
    items = (
        query.order_by(Producto.nombre, Producto.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0
    return BusquedaResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_response(p) for p in items],
    )


@router.get("/{producto_id}", response_model=ProductoResponse)
def obtener_producto(
    producto_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> ProductoResponse:
    """Obtiene un producto por ID (lookup directo, no filtra inactivos)."""
    _ = current
    producto = _get_or_404(db, producto_id)
    db.refresh(producto)
    return _to_response(producto)


@router.put("/{producto_id}", response_model=ProductoResponse)
def actualizar_producto(
    producto_id: str,
    data: ProductoUpdate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ProductoResponse:
    """Actualiza campos de un producto; precio_venta se recalcula (D1)."""
    _ = current
    producto = _get_or_404(db, producto_id)
    if data.sku is not None and data.sku != producto.sku:
        existente = db.query(Producto).filter_by(sku=data.sku).one_or_none()
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="sku ya registrado",
            )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(producto, field, value)
    db.commit()
    db.refresh(producto)
    return _to_response(producto)


@router.patch("/{producto_id}/margen-minimo", response_model=ProductoResponse)
def actualizar_margen_minimo(
    producto_id: str,
    data: MargenMinimoRequest,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ProductoResponse:
    """Actualiza margen_pct y/o stock minimo; precio_venta se recalcula (D1)."""
    _ = current
    producto = _get_or_404(db, producto_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(producto, field, value)
    db.commit()
    db.refresh(producto)
    return _to_response(producto)


@router.delete("/{producto_id}", status_code=204)
def eliminar_producto(
    producto_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (D2)."""
    _ = current
    producto = _get_or_404(db, producto_id)
    producto.activo = False
    db.commit()


@router.post("/{producto_id}/ajustar", response_model=AjusteStockResponse)
def ajustar_producto(
    producto_id: str,
    data: AjusteStockRequest,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> AjusteStockResponse:
    """Ajusta stock con movimiento auditable en 1 transaccion (RN-ST-02/03).

    Solo duena. Motivo obligatorio, delta != 0 (validados por schema
    antes de tocar la base). Resultado negativo -> 422 sin cambios.
    Fallo inesperado -> rollback total + 500, nunca stock a medias.
    """
    try:
        producto, movimiento = ajustar_stock(
            db,
            producto_id,
            data.cantidad_delta,
            data.motivo,
            current,
        )
    except ProductoNoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="producto no encontrado",
        ) from exc
    except (MotivoInvalido, StockNegativo, StockError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error interno al ajustar stock",
        ) from exc
    db.refresh(producto)
    return AjusteStockResponse(
        producto=_to_response(producto),
        movimiento=MovimientoResponse(
            id=movimiento.id,
            producto_id=movimiento.producto_id,
            tipo=movimiento.tipo,
            cantidad=movimiento.cantidad,
            stock_previo=movimiento.stock_previo,
            stock_nuevo=movimiento.stock_nuevo,
            ref_id=movimiento.ref_id,
            motivo=movimiento.motivo,
            usuario_id=movimiento.usuario_id,
            created_at=movimiento.created_at,
        ),
    )
