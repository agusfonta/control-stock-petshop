"""Productos router: CRUD + listado paginado (C-04).

Router delgado (C-16 D5): la logica vive en `productos.service`, que levanta
errores de dominio; aca se traducen a HTTP con el mismo status y detail.

Escritura (POST/PUT/DELETE) solo duena (D6); lectura cualquier usuario activo.
precio_venta es column_property (D1): se relee tras commit+refresh.
Soft-delete en DELETE (D2): activo=False, nunca borrado fisico.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import deps
from app.modules.productos import service as svc
from app.modules.productos.models import Producto
from app.modules.productos.schemas import (
    BusquedaResponse,
    MargenMinimoRequest,
    ProductoCreate,
    ProductoResponse,
    ProductoUpdate,
)
from app.modules.stock import service as stock_svc
from app.modules.stock.schemas import AjusteStockRequest, AjusteStockResponse, MovimientoResponse

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


def _http_error(exc: svc.ProductosError) -> HTTPException:
    """Traduce un error de dominio a su HTTPException (mismo status y detail)."""
    if isinstance(exc, svc.ProductoNoEncontrado):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="producto no encontrado")
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sku ya registrado")


def _busqueda(items: list[Producto], total: int, page: int, page_size: int) -> BusquedaResponse:
    """Envelope paginado de productos."""
    total_pages = math.ceil(total / page_size) if total else 0
    return BusquedaResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_response(p) for p in items],
    )


@router.post("", response_model=ProductoResponse, status_code=201)
def crear_producto(
    data: ProductoCreate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ProductoResponse:
    """Crea un producto; precio_venta se calcula solo (RN-PR-01)."""
    try:
        producto = svc.crear_producto(db, data, current)
    except svc.ProductosError as exc:
        raise _http_error(exc) from None
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
    items, total = svc.listar_productos(db, page, page_size)
    return _busqueda(items, total, page, page_size)


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
    items, total = svc.buscar_productos(db, q, page, page_size)
    return _busqueda(items, total, page, page_size)


@router.get("/{producto_id}", response_model=ProductoResponse)
def obtener_producto(
    producto_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> ProductoResponse:
    """Obtiene un producto por ID (lookup directo, no filtra inactivos)."""
    _ = current
    try:
        producto = svc.obtener_producto(db, producto_id)
    except svc.ProductosError as exc:
        raise _http_error(exc) from None
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
    try:
        producto = svc.actualizar_producto(db, producto_id, data)
    except svc.ProductosError as exc:
        raise _http_error(exc) from None
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
    try:
        producto = svc.actualizar_margen_minimo(db, producto_id, data)
    except svc.ProductosError as exc:
        raise _http_error(exc) from None
    return _to_response(producto)


@router.delete("/{producto_id}", status_code=204)
def eliminar_producto(
    producto_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (D2)."""
    _ = current
    try:
        svc.desactivar_producto(db, producto_id)
    except svc.ProductosError as exc:
        raise _http_error(exc) from None


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
        producto, movimiento = stock_svc.ajustar(
            db,
            producto_id,
            data.cantidad_delta,
            data.motivo,
            current,
        )
    except stock_svc.ProductoNoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="producto no encontrado",
        ) from exc
    except (stock_svc.MotivoInvalido, stock_svc.StockNegativo, stock_svc.StockError) as exc:
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
