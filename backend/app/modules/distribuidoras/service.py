"""Distribuidoras service: ABM, listas de precios y comparacion (C-06, extraido en C-16 D5).

No conoce HTTP: levanta errores de dominio que el router traduce a status y
detail. La baja de una distribuidora es logica (D6); quitar un producto de
una lista es baja fisica de la fila de costo.
"""

from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.distribuidoras.models import Distribuidora, ListaPrecio
from app.modules.distribuidoras.schemas import (
    CompararFila,
    DistribuidoraCreate,
    DistribuidoraUpdate,
    ListaPrecioDistribuidoraCreate,
    ListaPrecioUpdate,
)
from app.modules.productos.models import Producto

__all__ = [
    "DistribuidorasError",
    "DistribuidoraNoEncontrada",
    "ProductoNoEncontrado",
    "ProductoYaEnLista",
    "EntradaNoEncontrada",
    "actualizar_costo_lista",
    "actualizar_distribuidora",
    "agregar_a_lista",
    "comparar_costos",
    "crear_distribuidora",
    "desactivar_distribuidora",
    "listar_distribuidoras",
    "listar_lista",
    "obtener_distribuidora",
    "quitar_de_lista",
]


class DistribuidorasError(Exception):
    """Base de los errores de dominio de distribuidoras."""


class DistribuidoraNoEncontrada(DistribuidorasError):
    """La distribuidora no existe."""


class ProductoNoEncontrado(DistribuidorasError):
    """El producto referenciado no existe."""


class ProductoYaEnLista(DistribuidorasError):
    """El par (distribuidora, producto) ya esta cargado en la lista."""


class EntradaNoEncontrada(DistribuidorasError):
    """El producto no esta en la lista de la distribuidora."""


def obtener_distribuidora(db: Session, distribuidora_id: str) -> Distribuidora:
    """Lookup directo por id (no filtra inactivas)."""
    distribuidora = db.get(Distribuidora, distribuidora_id)
    if distribuidora is None:
        raise DistribuidoraNoEncontrada(distribuidora_id)
    return distribuidora


def crear_distribuidora(db: Session, data: DistribuidoraCreate) -> Distribuidora:
    """Crea una distribuidora."""
    distribuidora = Distribuidora(
        nombre=data.nombre,
        contacto=data.contacto,
        cuit=data.cuit,
        condiciones=data.condiciones,
    )
    db.add(distribuidora)
    db.commit()
    db.refresh(distribuidora)
    return distribuidora


def listar_distribuidoras(db: Session, page: int, page_size: int) -> tuple[list[Distribuidora], int]:
    """Distribuidoras activas por fecha de alta: (items de la pagina, total)."""
    query = db.query(Distribuidora).filter(Distribuidora.activo.is_(True))
    total = query.count()
    items = (
        query.order_by(Distribuidora.created_at, Distribuidora.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def actualizar_distribuidora(db: Session, distribuidora_id: str, data: DistribuidoraUpdate) -> Distribuidora:
    """Actualiza campos de una distribuidora."""
    distribuidora = obtener_distribuidora(db, distribuidora_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(distribuidora, field, value)
    db.commit()
    db.refresh(distribuidora)
    return distribuidora


def desactivar_distribuidora(db: Session, distribuidora_id: str) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (D6)."""
    distribuidora = obtener_distribuidora(db, distribuidora_id)
    distribuidora.activo = False
    db.commit()


def comparar_costos(db: Session, producto_id: str) -> list[CompararFila]:
    """Compara costos por distribuidora activa con precio sugerido (RN-PR-01).

    Solo lectura: precio_sugerido = costo x (1 + margen_pct) se calcula al
    vuelo en Decimal, sin persistir nada (RN-PR-04). Ordenado por costo.
    """
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise ProductoNoEncontrado(producto_id)
    entradas = (
        db.query(ListaPrecio, Distribuidora)
        .join(Distribuidora, ListaPrecio.distribuidora_id == Distribuidora.id)
        .filter(
            ListaPrecio.producto_id == producto_id,
            Distribuidora.activo.is_(True),
        )
        .order_by(ListaPrecio.costo.asc())
        .all()
    )
    margen = Decimal(producto.margen_pct)
    return [
        CompararFila(
            distribuidora_id=distribuidora.id,
            distribuidora_nombre=distribuidora.nombre,
            costo=entrada.costo,
            precio_sugerido=Decimal(entrada.costo) * (1 + margen),
        )
        for entrada, distribuidora in entradas
    ]


def agregar_a_lista(db: Session, distribuidora_id: str, data: ListaPrecioDistribuidoraCreate) -> ListaPrecio:
    """Agrega un costo (distribuidora, producto) a la lista.

    Par unico: duplicado falla con `ProductoYaEnLista` (pre-check + catch
    IntegrityError por carrera).
    """
    obtener_distribuidora(db, distribuidora_id)
    producto = db.get(Producto, data.producto_id)
    if producto is None:
        raise ProductoNoEncontrado(data.producto_id)
    existente = (
        db.query(ListaPrecio)
        .filter_by(distribuidora_id=distribuidora_id, producto_id=data.producto_id)
        .one_or_none()
    )
    if existente is not None:
        raise ProductoYaEnLista(data.producto_id)
    entrada = ListaPrecio(
        distribuidora_id=distribuidora_id,
        producto_id=data.producto_id,
        costo=data.costo,
    )
    db.add(entrada)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProductoYaEnLista(data.producto_id) from None
    db.refresh(entrada)
    return entrada


def listar_lista(db: Session, distribuidora_id: str) -> list[ListaPrecio]:
    """Costos de una distribuidora, ordenados por producto_id."""
    obtener_distribuidora(db, distribuidora_id)
    return (
        db.query(ListaPrecio)
        .filter_by(distribuidora_id=distribuidora_id)
        .order_by(ListaPrecio.producto_id)
        .all()
    )


def _entrada(db: Session, distribuidora_id: str, producto_id: str) -> ListaPrecio:
    """Fila de la lista (distribuidora ya validada) o `EntradaNoEncontrada`."""
    entrada = (
        db.query(ListaPrecio)
        .filter_by(distribuidora_id=distribuidora_id, producto_id=producto_id)
        .one_or_none()
    )
    if entrada is None:
        raise EntradaNoEncontrada(producto_id)
    return entrada


def actualizar_costo_lista(
    db: Session, distribuidora_id: str, producto_id: str, data: ListaPrecioUpdate
) -> ListaPrecio:
    """Actualiza el costo de una entrada de la lista."""
    obtener_distribuidora(db, distribuidora_id)
    entrada = _entrada(db, distribuidora_id, producto_id)
    entrada.costo = data.costo
    db.commit()
    db.refresh(entrada)
    return entrada


def quitar_de_lista(db: Session, distribuidora_id: str, producto_id: str) -> None:
    """Quita un producto de la lista: baja fisica de la fila de costo.

    No afecta al producto ni a la distribuidora.
    """
    obtener_distribuidora(db, distribuidora_id)
    entrada = _entrada(db, distribuidora_id, producto_id)
    db.delete(entrada)
    db.commit()
