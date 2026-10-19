"""Distribuidoras router: CRUD (C-06 task 2.2).

Escritura (POST/PUT/DELETE) solo duena (guards C-03); lectura cualquier
usuario activo. Borrado = soft-delete (activo=False), nunca fisico (D6).
Las listas anidadas y /comparar llegan en los tasks 3.2 y 4.2.

Router delgado (C-16 D5): la logica vive en `distribuidoras.service`, que
levanta errores de dominio; aca se traducen a HTTP con el mismo status y detail.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import deps
from app.modules.distribuidoras import service as svc
from app.modules.distribuidoras.models import Distribuidora, ListaPrecio
from app.modules.distribuidoras.schemas import (
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

_HTTP_POR_ERROR: dict[type[svc.DistribuidorasError], tuple[int, str]] = {
    svc.DistribuidoraNoEncontrada: (status.HTTP_404_NOT_FOUND, "distribuidora no encontrada"),
    svc.ProductoNoEncontrado: (status.HTTP_404_NOT_FOUND, "producto no encontrado"),
    svc.ProductoYaEnLista: (status.HTTP_409_CONFLICT, "producto ya cargado en esta lista"),
    svc.EntradaNoEncontrada: (status.HTTP_404_NOT_FOUND, "entrada no encontrada en la lista"),
}


def _http_error(exc: svc.DistribuidorasError) -> HTTPException:
    """Traduce un error de dominio a su HTTPException (mismo status y detail)."""
    codigo, detalle = _HTTP_POR_ERROR[type(exc)]
    return HTTPException(status_code=codigo, detail=detalle)


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
    return _to_response(svc.crear_distribuidora(db, data))


@router.get("", response_model=DistribuidoraListResponse)
def listar_distribuidoras(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> DistribuidoraListResponse:
    """Lista paginada de distribuidoras activas."""
    _ = current
    items, total = svc.listar_distribuidoras(db, page, page_size)
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
    try:
        filas = svc.comparar_costos(db, producto_id)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None
    return CompararResponse(producto_id=producto_id, filas=filas)


@router.get("/{distribuidora_id}", response_model=DistribuidoraResponse)
def obtener_distribuidora(
    distribuidora_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> DistribuidoraResponse:
    """Obtiene una distribuidora por ID (lookup directo, no filtra inactivos)."""
    _ = current
    try:
        distribuidora = svc.obtener_distribuidora(db, distribuidora_id)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None
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
    try:
        distribuidora = svc.actualizar_distribuidora(db, distribuidora_id, data)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None
    return _to_response(distribuidora)


@router.delete("/{distribuidora_id}", status_code=204)
def eliminar_distribuidora(
    distribuidora_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (D6)."""
    _ = current
    try:
        svc.desactivar_distribuidora(db, distribuidora_id)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None


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
    try:
        entrada = svc.agregar_a_lista(db, distribuidora_id, data)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None
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
    try:
        entradas = svc.listar_lista(db, distribuidora_id)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None
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
    try:
        entrada = svc.actualizar_costo_lista(db, distribuidora_id, producto_id, data)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None
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
    try:
        svc.quitar_de_lista(db, distribuidora_id, producto_id)
    except svc.DistribuidorasError as exc:
        raise _http_error(exc) from None
