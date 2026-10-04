"""Distribuidoras router: CRUD (C-06 task 2.2).

Escritura (POST/PUT/DELETE) solo duena (guards C-03); lectura cualquier
usuario activo. Borrado = soft-delete (activo=False), nunca fisico (D6).
Las listas anidadas y /comparar llegan en los tasks 3.2 y 4.2.
"""

import math

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import deps
from app.models import Distribuidora, ListaPrecio, Producto
from app.schemas import (
    CompararFila,
    CompararResponse,
    DistribuidoraCreate,
    DistribuidoraListResponse,
    DistribuidoraResponse,
    DistribuidoraUpdate,
    ListaPrecioDistribuidoraCreate,
    ListaPrecioResponse,
    ListaPrecioUpdate,
)

router = APIRouter(prefix="/distribuidoras", tags=["distribuidoras"])

MAX_PAGE_SIZE = 100


def _to_response(distribuidora: Distribuidora) -> DistribuidoraResponse:
    """Serializa el ORM a DistribuidoraResponse."""
    return DistribuidoraResponse(
        id=distribuidora.id,
        nombre=distribuidora.nombre,
        contacto=distribuidora.contacto,
        cuit=distribuidora.cuit,
        condiciones=distribuidora.condiciones,
        activo=distribuidora.activo,
        created_at=distribuidora.created_at,
        updated_at=distribuidora.updated_at,
    )


def _get_or_404(db: Session, distribuidora_id: str) -> Distribuidora:
    distribuidora = db.get(Distribuidora, distribuidora_id)
    if distribuidora is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="distribuidora no encontrada",
        )
    return distribuidora


def _to_lista_response(entrada: ListaPrecio) -> ListaPrecioResponse:
    """Serializa una fila de lista de precios."""
    return ListaPrecioResponse(
        id=entrada.id,
        distribuidora_id=entrada.distribuidora_id,
        producto_id=entrada.producto_id,
        costo=entrada.costo,
        activo=entrada.activo,
        created_at=entrada.created_at,
        updated_at=entrada.updated_at,
    )


@router.post("", response_model=DistribuidoraResponse, status_code=201)
def crear_distribuidora(
    data: DistribuidoraCreate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> DistribuidoraResponse:
    """Crea una distribuidora (solo duena)."""
    _ = current
    distribuidora = Distribuidora(
        nombre=data.nombre,
        contacto=data.contacto,
        cuit=data.cuit,
        condiciones=data.condiciones,
    )
    db.add(distribuidora)
    db.commit()
    db.refresh(distribuidora)
    return _to_response(distribuidora)


@router.get("", response_model=DistribuidoraListResponse)
def listar_distribuidoras(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> DistribuidoraListResponse:
    """Lista paginada de distribuidoras activas."""
    _ = current
    query = db.query(Distribuidora).filter(Distribuidora.activo.is_(True))
    total = query.count()
    items = (
        query.order_by(Distribuidora.created_at, Distribuidora.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0
    return DistribuidoraListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_response(d) for d in items],
    )


@router.get("/comparar", response_model=CompararResponse)
def comparar_costos(
    producto_id: str = Query(min_length=1),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> CompararResponse:
    """Compara costos por distribuidora activa con precio sugerido (RN-PR-01).

    D5: declarada ANTES que /{distribuidora_id} para no ser tragada como
    un id. Solo lectura: precio_sugerido = costo x (1 + margen_pct) se
    calcula al vuelo en Decimal, sin persistir nada (RN-PR-04).
    """
    _ = current
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="producto no encontrado",
        )
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
    filas = [
        CompararFila(
            distribuidora_id=distribuidora.id,
            distribuidora_nombre=distribuidora.nombre,
            costo=entrada.costo,
            precio_sugerido=Decimal(entrada.costo) * (1 + margen),
        )
        for entrada, distribuidora in entradas
    ]
    return CompararResponse(producto_id=producto_id, filas=filas)


@router.get("/{distribuidora_id}", response_model=DistribuidoraResponse)
def obtener_distribuidora(
    distribuidora_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> DistribuidoraResponse:
    """Obtiene una distribuidora por ID (lookup directo, no filtra inactivos)."""
    _ = current
    distribuidora = _get_or_404(db, distribuidora_id)
    db.refresh(distribuidora)
    return _to_response(distribuidora)


@router.put("/{distribuidora_id}", response_model=DistribuidoraResponse)
def actualizar_distribuidora(
    distribuidora_id: str,
    data: DistribuidoraUpdate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> DistribuidoraResponse:
    """Actualiza campos de una distribuidora (solo duena)."""
    _ = current
    distribuidora = _get_or_404(db, distribuidora_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(distribuidora, field, value)
    db.commit()
    db.refresh(distribuidora)
    return _to_response(distribuidora)


@router.delete("/{distribuidora_id}", status_code=204)
def eliminar_distribuidora(
    distribuidora_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (D6)."""
    _ = current
    distribuidora = _get_or_404(db, distribuidora_id)
    distribuidora.activo = False
    db.commit()


@router.post(
    "/{distribuidora_id}/listas",
    response_model=ListaPrecioResponse,
    status_code=201,
)
def agregar_a_lista(
    distribuidora_id: str,
    data: ListaPrecioDistribuidoraCreate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ListaPrecioResponse:
    """Agrega un costo (distribuidora, producto) a la lista (solo duena).

    Par unico: duplicado responde 409 (pre-check + catch IntegrityError
    por carrera, como el SKU en productos.py:97-105).
    """
    _ = current
    _get_or_404(db, distribuidora_id)
    producto = db.get(Producto, data.producto_id)
    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="producto no encontrado",
        )
    existente = (
        db.query(ListaPrecio)
        .filter_by(
            distribuidora_id=distribuidora_id, producto_id=data.producto_id
        )
        .one_or_none()
    )
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="producto ya cargado en esta lista",
        )
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="producto ya cargado en esta lista",
        ) from None
    db.refresh(entrada)
    return _to_lista_response(entrada)


@router.get(
    "/{distribuidora_id}/listas", response_model=list[ListaPrecioResponse]
)
def listar_lista(
    distribuidora_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> list[ListaPrecioResponse]:
    """Lista los costos de una distribuidora (cualquier usuario activo)."""
    _ = current
    _get_or_404(db, distribuidora_id)
    entradas = (
        db.query(ListaPrecio)
        .filter_by(distribuidora_id=distribuidora_id)
        .order_by(ListaPrecio.producto_id)
        .all()
    )
    return [_to_lista_response(e) for e in entradas]


@router.put(
    "/{distribuidora_id}/listas/{producto_id}",
    response_model=ListaPrecioResponse,
)
def actualizar_costo_lista(
    distribuidora_id: str,
    producto_id: str,
    data: ListaPrecioUpdate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ListaPrecioResponse:
    """Actualiza el costo de una entrada de la lista (solo duena)."""
    _ = current
    _get_or_404(db, distribuidora_id)
    entrada = (
        db.query(ListaPrecio)
        .filter_by(distribuidora_id=distribuidora_id, producto_id=producto_id)
        .one_or_none()
    )
    if entrada is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="entrada no encontrada en la lista",
        )
    entrada.costo = data.costo
    db.commit()
    db.refresh(entrada)
    return _to_lista_response(entrada)


@router.delete("/{distribuidora_id}/listas/{producto_id}", status_code=204)
def quitar_de_lista(
    distribuidora_id: str,
    producto_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Quita un producto de la lista: baja fisica de la fila de costo.

    No afecta al producto ni a la distribuidora.
    """
    _ = current
    _get_or_404(db, distribuidora_id)
    entrada = (
        db.query(ListaPrecio)
        .filter_by(distribuidora_id=distribuidora_id, producto_id=producto_id)
        .one_or_none()
    )
    if entrada is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="entrada no encontrada en la lista",
        )
    db.delete(entrada)
    db.commit()
