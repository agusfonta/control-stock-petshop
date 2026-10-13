"""Clientes router: alta, consulta, edicion y baja (C-09).

Alta para duena y mostrador (matriz RBAC "ver + crear", D3); edicion y baja
(soft-delete, activo=False) solo duena; lectura cualquier usuario activo.
Email unico entre clientes activos (D5, 409); telefono y nombre no son
unicos. `saldo_cc` esta reservado y nunca se expone (D8). La busqueda
`/buscar` (task 5.2) va ANTES que `/{cliente_id}` (D7).

Router delgado (C-16 D5): la logica vive en `clientes.service`, que levanta
errores de dominio; aca se traducen a HTTP con el mismo status y detail.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import deps
from app.modules.clientes import service as svc
from app.modules.clientes.models import Cliente
from app.modules.clientes.schemas import ClienteCreate, ClienteListResponse, ClienteResponse, ClienteUpdate
from app.modules.ventas import service as ventas_svc
from app.modules.ventas.schemas import VentaListResponse

router = APIRouter(prefix="/clientes", tags=["clientes"])

MAX_PAGE_SIZE = 100


def _to_response(cliente: Cliente) -> ClienteResponse:
    """Serializa el ORM a ClienteResponse (sin saldo_cc, D8)."""
    return ClienteResponse(
        id=cliente.id,
        nombre=cliente.nombre,
        telefono=cliente.telefono,
        email=cliente.email,
        direccion=cliente.direccion,
        activo=cliente.activo,
        created_at=cliente.created_at,
        updated_at=cliente.updated_at,
    )


def _http_error(exc: svc.ClientesError) -> HTTPException:
    """Traduce un error de dominio a su HTTPException (mismo status y detail)."""
    if isinstance(exc, svc.ClienteNoEncontrado):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cliente no encontrado")
    if isinstance(exc, svc.EmailEnUso):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email ya registrado")
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="q no puede estar en blanco")


def _lista(items: list[Cliente], total: int, page: int, page_size: int) -> ClienteListResponse:
    """Envelope paginado de clientes."""
    total_pages = math.ceil(total / page_size) if total else 0
    return ClienteListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[_to_response(c) for c in items],
    )


@router.post("", response_model=ClienteResponse, status_code=201)
def crear_cliente(
    data: ClienteCreate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_role("duena", "mostrador")),
) -> ClienteResponse:
    """Crea un cliente (duena o mostrador); email unico entre activos."""
    _ = current
    try:
        cliente = svc.crear_cliente(db, data)
    except svc.ClientesError as exc:
        raise _http_error(exc) from None
    return _to_response(cliente)


@router.get("", response_model=ClienteListResponse)
def listar_clientes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> ClienteListResponse:
    """Lista paginada de clientes activos, ordenados por nombre."""
    _ = current
    items, total = svc.listar_clientes(db, page, page_size)
    return _lista(items, total, page, page_size)


@router.get("/buscar", response_model=ClienteListResponse)
def buscar_clientes(
    q: str = Query(min_length=1, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> ClienteListResponse:
    """Busca clientes activos por nombre/email o digitos de telefono (D6).

    D7: declarada ANTES que /{cliente_id} para no ser tragada como un id.
    Insensible a mayusculas y acentos; `%` y `_` de `q` no son comodines. La
    rama de telefono solo aplica si `q` tiene digitos (con `%%` matchearia todo).
    """
    _ = current
    try:
        items, total = svc.buscar_clientes(db, q, page, page_size)
    except svc.ClientesError as exc:
        raise _http_error(exc) from None
    return _lista(items, total, page, page_size)


@router.get("/{cliente_id}", response_model=ClienteResponse)
def obtener_cliente(
    cliente_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> ClienteResponse:
    """Obtiene un cliente por ID (lookup directo, no filtra inactivos, D9)."""
    _ = current
    try:
        return _to_response(svc.obtener_cliente(db, cliente_id))
    except svc.ClientesError as exc:
        raise _http_error(exc) from None


@router.get("/{cliente_id}/ventas", response_model=VentaListResponse)
def historial_ventas(
    cliente_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> VentaListResponse:
    """Historial de ventas del cliente (C-10, D12/D15).

    Confirmadas y anuladas, mas reciente primero; el mostrador ve solo las
    que registro. Un cliente dado de baja conserva su historial (200).
    """
    try:
        items, total = ventas_svc.ventas_de_cliente(
            db, cliente_id, current, page, page_size
        )
    except ventas_svc.NoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="cliente no encontrado",
        ) from None
    return ventas_svc.to_venta_list_response(items, total, page, page_size)


@router.put("/{cliente_id}", response_model=ClienteResponse)
def actualizar_cliente(
    cliente_id: str,
    data: ClienteUpdate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ClienteResponse:
    """Actualiza parcialmente un cliente (solo duena); email unico entre activos."""
    _ = current
    try:
        cliente = svc.actualizar_cliente(db, cliente_id, data)
    except svc.ClientesError as exc:
        raise _http_error(exc) from None
    return _to_response(cliente)


@router.delete("/{cliente_id}", status_code=204)
def eliminar_cliente(
    cliente_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (solo duena)."""
    _ = current
    try:
        svc.desactivar_cliente(db, cliente_id)
    except svc.ClientesError as exc:
        raise _http_error(exc) from None
