"""Clientes service: acceso a datos y reglas de clientes (C-09, extraido en C-16 D5).

No conoce HTTP: levanta errores de dominio que el router traduce a status y
detail. Email unico entre clientes ACTIVOS (D5, sin distinguir mayusculas);
telefono y nombre no son unicos. La busqueda ignora mayusculas y acentos (D6).
"""

from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.core.texto import PARES_PLEGADO, sin_acentos, solo_digitos
from app.modules.clientes.models import Cliente, Mascota
from app.modules.clientes.schemas import ClienteCreate, ClienteUpdate, MascotaCreate, MascotaUpdate

__all__ = [
    "ClientesError",
    "ClienteNoEncontrado",
    "MascotaNoEncontrada",
    "ClienteInactivo",
    "EmailEnUso",
    "BusquedaVacia",
    "actualizar_cliente",
    "actualizar_mascota",
    "buscar_clientes",
    "crear_cliente",
    "crear_mascota",
    "desactivar_cliente",
    "desactivar_mascota",
    "listar_clientes",
    "listar_mascotas",
    "obtener_cliente",
]


class ClientesError(Exception):
    """Base de los errores de dominio de clientes."""


class ClienteNoEncontrado(ClientesError):
    """El cliente no existe."""


class ClienteInactivo(ClientesError):
    """El cliente esta dado de baja: no admite altas ni ediciones de mascotas."""


class MascotaNoEncontrada(ClientesError):
    """La mascota no existe, esta dada de baja o no pertenece al cliente."""


class EmailEnUso(ClientesError):
    """Otro cliente ACTIVO ya usa el email."""


class BusquedaVacia(ClientesError):
    """El texto de busqueda queda en blanco tras normalizarlo."""


def obtener_cliente(db: Session, cliente_id: str) -> Cliente:
    """Lookup directo por id (no filtra inactivos, D9)."""
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise ClienteNoEncontrado(cliente_id)
    return cliente


def _verificar_email_libre(db: Session, email: str | None, excluir_id: str | None = None) -> None:
    """Falla si otro cliente ACTIVO ya usa el email (sin distinguir mayusculas)."""
    if email is None:
        return
    query = db.query(Cliente.id).filter(
        Cliente.activo.is_(True),
        func.lower(Cliente.email) == email.lower(),
    )
    if excluir_id is not None:
        query = query.filter(Cliente.id != excluir_id)
    if query.first() is not None:
        raise EmailEnUso(email)


def _paginar(query: Query, page: int, page_size: int) -> tuple[list[Cliente], int]:
    """Aplica orden (nombre, id) y paginado offset-based; devuelve (items, total)."""
    total = query.count()
    items = query.order_by(Cliente.nombre, Cliente.id).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def _nueva_mascota(cliente_id: str, data: MascotaCreate) -> Mascota:
    """Mascota nueva con created_at explicito (orden estable)."""
    return Mascota(
        cliente_id=cliente_id,
        nombre=data.nombre,
        tipo=data.tipo,
        created_at=datetime.now(timezone.utc),
    )


def crear_cliente(db: Session, data: ClienteCreate) -> Cliente:
    """Crea un cliente; email unico entre activos."""
    _verificar_email_libre(db, data.email)
    cliente = Cliente(
        nombre=data.nombre,
        telefono=data.telefono,
        email=data.email,
        direccion=data.direccion,
    )
    try:
        db.add(cliente)
        if data.mascota is not None:
            db.flush()
            db.add(_nueva_mascota(cliente.id, data.mascota))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(cliente)
    return cliente


def listar_clientes(db: Session, page: int, page_size: int) -> tuple[list[Cliente], int]:
    """Clientes activos ordenados por nombre: (items de la pagina, total)."""
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


def buscar_clientes(db: Session, q: str, page: int, page_size: int) -> tuple[list[Cliente], int]:
    """Busca clientes activos por nombre/email o digitos de telefono (D6).

    Insensible a mayusculas y acentos; `%` y `_` de `q` no son comodines. La
    rama de telefono solo aplica si `q` tiene digitos (con `%%` matchearia todo).
    """
    texto = sin_acentos(q)
    if not texto:
        raise BusquedaVacia(q)
    condiciones = [
        _nombre_plegado().contains(texto, autoescape=True),
        func.lower(Cliente.email).contains(texto, autoescape=True),
    ]
    digitos = solo_digitos(q)
    if digitos:
        condiciones.append(Cliente.telefono.contains(digitos, autoescape=True))
    query = db.query(Cliente).filter(Cliente.activo.is_(True), or_(*condiciones))
    return _paginar(query, page, page_size)


def actualizar_cliente(db: Session, cliente_id: str, data: ClienteUpdate) -> Cliente:
    """Actualiza parcialmente un cliente; email unico entre activos."""
    cliente = obtener_cliente(db, cliente_id)
    cambios = data.model_dump(exclude_unset=True)
    _verificar_email_libre(db, cambios.get("email"), excluir_id=cliente.id)
    for field, value in cambios.items():
        setattr(cliente, field, value)
    db.commit()
    db.refresh(cliente)
    return cliente


def desactivar_cliente(db: Session, cliente_id: str) -> None:
    """Soft-delete: marca activo=False, nunca borra fisico."""
    cliente = obtener_cliente(db, cliente_id)
    cliente.activo = False
    db.commit()


# --- C-17: mascotas ---


def _obtener_cliente_activo(db: Session, cliente_id: str) -> Cliente:
    """Cliente existente y activo; de baja -> ClienteInactivo."""
    cliente = obtener_cliente(db, cliente_id)
    if not cliente.activo:
        raise ClienteInactivo(cliente_id)
    return cliente


def _obtener_mascota(db: Session, cliente_id: str, mascota_id: str) -> Mascota:
    """Mascota ACTIVA del cliente; el cliente inexistente prevalece (404 distinto)."""
    obtener_cliente(db, cliente_id)
    mascota = (
        db.query(Mascota)
        .filter(Mascota.id == mascota_id, Mascota.cliente_id == cliente_id, Mascota.activo.is_(True))
        .first()
    )
    if mascota is None:
        raise MascotaNoEncontrada(mascota_id)
    return mascota


def crear_mascota(db: Session, cliente_id: str, data: MascotaCreate) -> Mascota:
    """Crea una mascota del cliente (created_at explicito: orden estable)."""
    _obtener_cliente_activo(db, cliente_id)
    mascota = _nueva_mascota(cliente_id, data)
    db.add(mascota)
    db.commit()
    db.refresh(mascota)
    return mascota


def listar_mascotas(db: Session, cliente_id: str) -> list[Mascota]:
    """Mascotas activas del cliente, en orden de creacion."""
    obtener_cliente(db, cliente_id)
    return (
        db.query(Mascota)
        .filter(Mascota.cliente_id == cliente_id, Mascota.activo.is_(True))
        .order_by(Mascota.created_at, Mascota.id)
        .all()
    )


def actualizar_mascota(db: Session, cliente_id: str, mascota_id: str, data: MascotaUpdate) -> Mascota:
    """Actualiza parcialmente una mascota activa del cliente (cliente activo)."""
    _obtener_cliente_activo(db, cliente_id)
    mascota = _obtener_mascota(db, cliente_id, mascota_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(mascota, field, value)
    db.commit()
    db.refresh(mascota)
    return mascota


def desactivar_mascota(db: Session, cliente_id: str, mascota_id: str) -> None:
    """Baja logica: activo=False, nunca borra fisico."""
    mascota = _obtener_mascota(db, cliente_id, mascota_id)
    mascota.activo = False
    db.commit()
