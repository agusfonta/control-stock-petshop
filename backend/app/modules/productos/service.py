"""Productos service: catalogo, busqueda y baja logica (C-04, extraido en C-16 D5).

No conoce HTTP: levanta errores de dominio que el router traduce a status y
detail. El stock inicial viaja con su movimiento de apertura via
`stock.service.aplicar_movimiento` (RN-ST-03); el service de stock sigue
siendo el unico que muta stock.
"""

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import Usuario
from app.modules.productos.models import Producto
from app.modules.productos.schemas import MargenMinimoRequest, ProductoCreate, ProductoUpdate
from app.modules.stock.service import aplicar_movimiento

__all__ = [
    "ProductosError",
    "ProductoNoEncontrado",
    "SkuDuplicado",
    "actualizar_margen_minimo",
    "actualizar_producto",
    "buscar_productos",
    "crear_producto",
    "desactivar_producto",
    "listar_productos",
    "obtener_producto",
]


class ProductosError(Exception):
    """Base de los errores de dominio de productos."""


class ProductoNoEncontrado(ProductosError):
    """El producto no existe."""


class SkuDuplicado(ProductosError):
    """Ya existe un producto con ese SKU."""


def obtener_producto(db: Session, producto_id: str) -> Producto:
    """Lookup directo por id (no filtra inactivos)."""
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise ProductoNoEncontrado(producto_id)
    return producto


def crear_producto(db: Session, data: ProductoCreate, usuario: Usuario) -> Producto:
    """Crea un producto; precio_venta se calcula solo (RN-PR-01)."""
    existente = db.query(Producto).filter_by(sku=data.sku).one_or_none()
    if existente is not None:
        raise SkuDuplicado(data.sku)
    producto = Producto(
        sku=data.sku,
        nombre=data.nombre,
        marca=data.marca,
        categoria=data.categoria,
        unidad=data.unidad,
        costo=data.costo,
        margen_pct=data.margen_pct,
        stock_actual=0,
        stock_minimo=data.stock_minimo,
        distribuidora_default_id=data.distribuidora_default_id,
    )
    db.add(producto)
    try:
        db.flush()
        if data.stock_actual > 0:
            # RN-ST-03: el stock inicial viaja con su movimiento de apertura.
            aplicar_movimiento(
                db, producto.id, data.stock_actual, "apertura", usuario,
                motivo="stock inicial",
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise SkuDuplicado(data.sku) from None
    db.refresh(producto)
    return producto


def listar_productos(db: Session, page: int, page_size: int) -> tuple[list[Producto], int]:
    """Productos activos por fecha de alta: (items de la pagina, total)."""
    query = db.query(Producto).filter(Producto.activo.is_(True))
    total = query.count()
    items = (
        query.order_by(Producto.created_at, Producto.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def buscar_productos(db: Session, q: str, page: int, page_size: int) -> tuple[list[Producto], int]:
    """Busca por SKU exacto o nombre parcial (D3): (items de la pagina, total).

    OR(sku == q, nombre ILIKE %q%): el ILIKE usa el indice trgm en Postgres
    y es case-insensitive en SQLite (tests).
    """
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
    return items, total


def actualizar_producto(db: Session, producto_id: str, data: ProductoUpdate) -> Producto:
    """Actualiza campos de un producto; precio_venta se recalcula (D1)."""
    producto = obtener_producto(db, producto_id)
    if data.sku is not None and data.sku != producto.sku:
        existente = db.query(Producto).filter_by(sku=data.sku).one_or_none()
        if existente is not None:
            raise SkuDuplicado(data.sku)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(producto, field, value)
    db.commit()
    db.refresh(producto)
    return producto


def actualizar_margen_minimo(db: Session, producto_id: str, data: MargenMinimoRequest) -> Producto:
    """Actualiza margen_pct y/o stock minimo; precio_venta se recalcula (D1)."""
    producto = obtener_producto(db, producto_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(producto, field, value)
    db.commit()
    db.refresh(producto)
    return producto


def desactivar_producto(db: Session, producto_id: str) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (D2)."""
    producto = obtener_producto(db, producto_id)
    producto.activo = False
    db.commit()
