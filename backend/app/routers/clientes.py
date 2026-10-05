"""Clientes router: alta, consulta, edicion y baja (C-09).

Alta para duena y mostrador (matriz RBAC "ver + crear", D3); edicion y baja
(soft-delete, activo=False) solo duena; lectura cualquier usuario activo.
Email unico entre clientes activos (D5, 409); telefono y nombre no son
unicos. `saldo_cc` esta reservado y nunca se expone (D8). La busqueda
`/buscar` (task 5.2) va ANTES que `/{cliente_id}` (D7).
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import deps
from app.core.texto import PARES_PLEGADO, sin_acentos, solo_digitos
from app.models import Cliente
from app.schemas import (
    ClienteCreate,
    ClienteListResponse,
    ClienteResponse,
    ClienteUpdate,
)

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


def _get_or_404(db: Session, cliente_id: str) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="cliente no encontrado",
        )
    return cliente


def _verificar_email_libre(
    db: Session, email: str | None, excluir_id: str | None = None
) -> None:
    """409 si otro cliente ACTIVO ya usa el email (sin distinguir mayusculas)."""
    if email is None:
        return
    query = db.query(Cliente.id).filter(
        Cliente.activo.is_(True),
        func.lower(Cliente.email) == email.lower(),
    )
    if excluir_id is not None:
        query = query.filter(Cliente.id != excluir_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email ya registrado",
        )


def _paginar(query, page: int, page_size: int) -> ClienteListResponse:
    """Aplica orden (nombre, id) y paginado offset-based a una query de clientes."""
    total = query.count()
    items = (
        query.order_by(Cliente.nombre, Cliente.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
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
    _verificar_email_libre(db, data.email)
    cliente = Cliente(
        nombre=data.nombre,
        telefono=data.telefono,
        email=data.email,
        direccion=data.direccion,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
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
    query = db.query(Cliente).filter(Cliente.activo.is_(True))
    return _paginar(query, page, page_size)


def _nombre_plegado():
    """Expresion SQL del nombre en minusculas y sin acentos (D6).

    `replace()` anidados portables a SQLite y Postgres; se reemplazan tambien
    las mayusculas acentuadas porque `lower()` de SQLite solo baja ASCII.
    """
    expr = Cliente.nombre
    for acentuado, base in PARES_PLEGADO:
        expr = func.replace(expr, acentuado, base)
    return func.lower(expr)


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
    texto = sin_acentos(q)
    if not texto:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="q no puede estar en blanco",
        )
    condiciones = [
        _nombre_plegado().contains(texto, autoescape=True),
        func.lower(Cliente.email).contains(texto, autoescape=True),
    ]
    digitos = solo_digitos(q)
    if digitos:
        condiciones.append(Cliente.telefono.contains(digitos, autoescape=True))
    query = db.query(Cliente).filter(Cliente.activo.is_(True), or_(*condiciones))
    return _paginar(query, page, page_size)


@router.get("/{cliente_id}", response_model=ClienteResponse)
def obtener_cliente(
    cliente_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.get_current_user),
) -> ClienteResponse:
    """Obtiene un cliente por ID (lookup directo, no filtra inactivos, D9)."""
    _ = current
    return _to_response(_get_or_404(db, cliente_id))


@router.put("/{cliente_id}", response_model=ClienteResponse)
def actualizar_cliente(
    cliente_id: str,
    data: ClienteUpdate,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> ClienteResponse:
    """Actualiza parcialmente un cliente (solo duena); email unico entre activos."""
    _ = current
    cliente = _get_or_404(db, cliente_id)
    cambios = data.model_dump(exclude_unset=True)
    _verificar_email_libre(db, cambios.get("email"), excluir_id=cliente.id)
    for field, value in cambios.items():
        setattr(cliente, field, value)
    db.commit()
    db.refresh(cliente)
    return _to_response(cliente)


@router.delete("/{cliente_id}", status_code=204)
def eliminar_cliente(
    cliente_id: str,
    db: Session = Depends(deps.get_db),
    current: deps.Usuario = Depends(deps.require_duena),
) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico (solo duena)."""
    _ = current
    cliente = _get_or_404(db, cliente_id)
    cliente.activo = False
    db.commit()
