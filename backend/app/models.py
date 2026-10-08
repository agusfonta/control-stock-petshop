"""Domain ORM models (C-02 core-models).

Single module by design (split only when sales/purchases arrive in C-05).
Money as Numeric; precio_venta is a read-time column_property (RN-PR-01);
roles as native Enum (duena/mostrador). Auth logic belongs to C-03.
"""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import column_property, relationship

from app.core.db import Base

__all__ = [
    "Base",
    "AuditMixin",
    "Usuario",
    "Producto",
    "ListaPrecio",
    "Distribuidora",
    "Cliente",
    "MovimientoStock",
    "PedidoCompra",
    "LineaPedido",
    "EntradaStock",
    "PagoDistribuidora",
    "Venta",
    "LineaVenta",
    "PagoVenta",
    "EventoOutbox",
]

ROL_USUARIO = ("duena", "mostrador")
UNIDAD_PRODUCTO = ("unidad", "bolsa", "caja")
TIPO_MOVIMIENTO = ("venta", "entrada", "ajuste", "apertura")
ESTADO_PEDIDO = ("pendiente", "recibido", "cancelado")
METODO_PAGO_DISTRIBUIDORA = ("efectivo", "transferencia", "cheque", "otro")
ESTADO_VENTA = ("borrador", "confirmada", "anulada")
METODO_PAGO_VENTA = ("efectivo", "transferencia", "mp", "tarjeta")


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditMixin:
    """activo soft-delete flag + server-managed audit timestamps."""

    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Usuario(Base, AuditMixin):
    """App user. Password hashing/verification belongs to C-03 (auth)."""

    __tablename__ = "usuarios"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    rol = Column(Enum(*ROL_USUARIO, name="rol_usuario"), nullable=False)


class Distribuidora(Base, AuditMixin):
    """Supplier/distributor of products."""

    __tablename__ = "distribuidoras"

    id = Column(String(36), primary_key=True, default=_uuid)
    nombre = Column(String, nullable=False)
    contacto = Column(String, nullable=True)
    cuit = Column(String, nullable=True)
    condiciones = Column(String, nullable=True)

class Producto(Base, AuditMixin):
    """Sellable item. precio_venta is always costo*(1+margen) (RN-PR-01)."""

    __tablename__ = "productos"
    __table_args__ = (
        CheckConstraint("stock_actual >= 0", name="ck_productos_stock_no_negativo"),
        # GIN/trgm on Postgres; plain index elsewhere (SQLite ignores
        # postgresql_* kwargs). Mirrors 0002 (raw CREATE INDEX for the opclass).
        Index(
            "ix_productos_nombre_trgm",
            "nombre",
            postgresql_using="gin",
            postgresql_ops={"nombre": "gin_trgm_ops"},
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    sku = Column(String, nullable=False, unique=True)
    nombre = Column(String, nullable=False)
    marca = Column(String, nullable=True)
    categoria = Column(String, nullable=True, index=True)
    unidad = Column(
        Enum(*UNIDAD_PRODUCTO, name="unidad_producto"),
        nullable=False,
        default="unidad",
        server_default="unidad",
    )
    costo = Column(Numeric(10, 2), nullable=False)
    margen_pct = Column(Numeric(5, 4), nullable=False, default=0)
    stock_actual = Column(Integer, nullable=False, default=0, server_default="0")
    stock_minimo = Column(Integer, nullable=False, default=0, server_default="0")
    distribuidora_default_id = Column(
        String(36),
        ForeignKey("distribuidoras.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )


# Read-time price (no physical column, no triggers): RN-PR-01 always current.
# NOTE: transient instances (never flushed) cannot evaluate this expression;
# flush/commit + refresh before reading precio_venta.
Producto.precio_venta = column_property(Producto.costo * (1 + Producto.margen_pct))


class ListaPrecio(Base, AuditMixin):
    """Costo de un producto por distribuidora (RN-PR-03). Persistence only in
    C-04 — the per-distributor price calculation arrives with C-06/C-07."""

    __tablename__ = "lista_precio"
    __table_args__ = (
        # One cost per (distribuidora, producto) pair.
        UniqueConstraint(
            "distribuidora_id",
            "producto_id",
            name="uq_lista_precio_distribuidora_producto",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    distribuidora_id = Column(
        String(36),
        ForeignKey("distribuidoras.id"),
        nullable=False,
    )
    producto_id = Column(
        String(36),
        ForeignKey("productos.id"),
        nullable=False,
    )
    costo = Column(Numeric(10, 2), nullable=False)

    distribuidora = relationship("Distribuidora", backref="lista_precios")
    producto = relationship("Producto", backref="lista_precios")


class Cliente(Base, AuditMixin):
    """Counter customer, optionally with cuenta-corriente balance."""

    __tablename__ = "clientes"

    id = Column(String(36), primary_key=True, default=_uuid)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    saldo_cc = Column(Numeric(10, 2), nullable=False, default=0, server_default="0")


class MovimientoStock(Base):
    """Append-only ledger of every stock change (C-05, RN-ST-03).

    One row per mutation with signed cantidad + stock_previo/stock_nuevo.
    No updated_at/activo: rows are never modified. ORM-level UPDATE/DELETE
    are blocked via event listeners (decision D7); the DB check on
    stock_nuevo is the last barrier (defense in depth with Pydantic).
    Stock before C-05 has no rows: it counts as opening balance (no backfill).
    """

    __tablename__ = "movimiento_stock"
    __table_args__ = (
        CheckConstraint(
            "stock_nuevo >= 0", name="ck_movimiento_stock_nuevo_no_negativo"
        ),
        Index("ix_movimiento_stock_producto_id", "producto_id"),
        Index("ix_movimiento_stock_created_at", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    producto_id = Column(
        String(36),
        ForeignKey("productos.id"),
        nullable=False,
    )
    tipo = Column(
        Enum(*TIPO_MOVIMIENTO, name="tipo_movimiento"),
        nullable=False,
    )
    cantidad = Column(Integer, nullable=False)
    stock_previo = Column(Integer, nullable=False)
    stock_nuevo = Column(Integer, nullable=False)
    ref_id = Column(String(36), nullable=True)
    motivo = Column(String, nullable=True)
    usuario_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    producto = relationship("Producto", backref="movimientos")
    usuario = relationship("Usuario", backref="movimientos_stock")


@event.listens_for(MovimientoStock, "before_update")
def _bloquear_update_movimiento(mapper, connection, target) -> None:
    """Reject any UPDATE: the ledger is insert-only (RN-ST-03)."""
    raise InvalidRequestError(
        "movimiento_stock es append-only: update bloqueado"
    )


@event.listens_for(MovimientoStock, "before_delete")
def _bloquear_delete_movimiento(mapper, connection, target) -> None:
    """Reject any DELETE: the ledger is insert-only (RN-ST-03)."""
    raise InvalidRequestError(
        "movimiento_stock es append-only: delete bloqueado"
    )


class PedidoCompra(Base, AuditMixin):
    """Pedido de mercaderia a una distribuidora (C-07, RN-CP-01/02).

    Nace pendiente y NO mueve stock; solo recibirlo lo hace (en una sola
    transaccion, ver services/compras.py). recibido/cancelado son estados
    finales. activo queda en true: la baja de un pedido es cancelarlo,
    nunca se borra (D2).
    """

    __tablename__ = "pedido_compra"
    __table_args__ = (
        Index("ix_pedido_compra_distribuidora_id", "distribuidora_id"),
        Index("ix_pedido_compra_estado", "estado"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    distribuidora_id = Column(
        String(36),
        ForeignKey("distribuidoras.id"),
        nullable=False,
    )
    estado = Column(
        Enum(*ESTADO_PEDIDO, name="estado_pedido"),
        nullable=False,
        default="pendiente",
        server_default="pendiente",
    )
    usuario_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    notas = Column(String, nullable=True)
    recibido_at = Column(DateTime(timezone=True), nullable=True)
    recibido_por_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=True,
    )

    distribuidora = relationship("Distribuidora", backref="pedidos_compra")
    lineas = relationship(
        "LineaPedido",
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="LineaPedido.producto_id",
    )
    entradas = relationship(
        "EntradaStock",
        back_populates="pedido",
        order_by="EntradaStock.producto_id",
    )


class LineaPedido(Base):
    """Linea de un pedido: producto, cantidad y costo pactado (D6).

    costo_unitario es el snapshot tomado al crear el pedido (lista de la
    distribuidora o costo del producto); un producto por pedido.
    """

    __tablename__ = "linea_pedido"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_linea_pedido_cantidad_positiva"),
        CheckConstraint(
            "costo_unitario > 0", name="ck_linea_pedido_costo_positivo"
        ),
        UniqueConstraint(
            "pedido_id", "producto_id", name="uq_linea_pedido_pedido_producto"
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    pedido_id = Column(
        String(36),
        ForeignKey("pedido_compra.id", ondelete="CASCADE"),
        nullable=False,
    )
    producto_id = Column(
        String(36),
        ForeignKey("productos.id"),
        nullable=False,
    )
    cantidad = Column(Integer, nullable=False)
    costo_unitario = Column(Numeric(10, 2), nullable=False)

    pedido = relationship("PedidoCompra", back_populates="lineas")
    producto = relationship("Producto")


class EntradaStock(Base):
    """Fila append-only por producto recibido de un pedido (C-07, D2).

    El MovimientoStock tipo entrada apunta a esta fila via ref_id. El
    unique (pedido_id, producto_id) es la barrera de base contra la doble
    recepcion (D7). Sin updated_at/activo: nunca se modifica.
    """

    __tablename__ = "entrada_stock"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_entrada_stock_cantidad_positiva"),
        CheckConstraint(
            "costo_unitario > 0", name="ck_entrada_stock_costo_positivo"
        ),
        UniqueConstraint(
            "pedido_id", "producto_id", name="uq_entrada_stock_pedido_producto"
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    pedido_id = Column(
        String(36),
        ForeignKey("pedido_compra.id"),
        nullable=False,
    )
    producto_id = Column(
        String(36),
        ForeignKey("productos.id"),
        nullable=False,
    )
    cantidad = Column(Integer, nullable=False)
    costo_unitario = Column(Numeric(10, 2), nullable=False)
    usuario_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    pedido = relationship("PedidoCompra", back_populates="entradas")
    producto = relationship("Producto")


@event.listens_for(EntradaStock, "before_update")
def _bloquear_update_entrada(mapper, connection, target) -> None:
    """Reject any UPDATE: las entradas son insert-only (C-07 D2)."""
    raise InvalidRequestError("entrada_stock es append-only: update bloqueado")


@event.listens_for(EntradaStock, "before_delete")
def _bloquear_delete_entrada(mapper, connection, target) -> None:
    """Reject any DELETE: las entradas son insert-only (C-07 D2)."""
    raise InvalidRequestError("entrada_stock es append-only: delete bloqueado")


class PagoDistribuidora(Base, AuditMixin):
    """Pago a una distribuidora, independiente de pedidos (RN-CP-03).

    Sin pedido_id. Anular = activo=False (soft-delete): el pago anulado
    no se lista ni suma en la cuenta (D9).
    """

    __tablename__ = "pago_distribuidora"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_pago_distribuidora_monto_positivo"),
        Index("ix_pago_distribuidora_distribuidora_id", "distribuidora_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    distribuidora_id = Column(
        String(36),
        ForeignKey("distribuidoras.id"),
        nullable=False,
    )
    monto = Column(Numeric(12, 2), nullable=False)
    metodo = Column(
        Enum(*METODO_PAGO_DISTRIBUIDORA, name="metodo_pago_distribuidora"),
        nullable=False,
    )
    fecha = Column(
        Date,
        nullable=False,
        default=date.today,
        server_default=func.current_date(),
    )
    nota = Column(String, nullable=True)
    usuario_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=False,
    )

    distribuidora = relationship("Distribuidora", backref="pagos")


class Venta(Base, AuditMixin):
    """Venta de mostrador (C-10, RN-VT-01..04).

    Nace `borrador` con lineas y total fijados por el servidor (D4/D5) y NO
    mueve stock; confirmarla lo descuenta junto con sus pagos en una sola
    transaccion (ver services/ventas.py). confirmada -> anulada es la unica
    otra transicion; `anulada` es final. `activo` queda siempre en true: las
    ventas nunca se borran. usuario_id es el vendedor/creador (propiedad,
    D12); la clave de idempotencia es unica por vendedor (D8).
    """

    __tablename__ = "venta"
    __table_args__ = (
        CheckConstraint("total > 0", name="ck_venta_total_positivo"),
        CheckConstraint(
            "estado = 'borrador' OR confirmada_at IS NOT NULL",
            name="ck_venta_confirmada_con_fecha",
        ),
        CheckConstraint(
            "estado <> 'anulada' OR "
            "(anulada_at IS NOT NULL AND motivo_anulacion IS NOT NULL)",
            name="ck_venta_anulada_con_fecha_y_motivo",
        ),
        UniqueConstraint(
            "usuario_id", "idempotency_key", name="uq_venta_usuario_idempotency_key"
        ),
        Index("ix_venta_cliente_id_created_at", "cliente_id", "created_at"),
        Index("ix_venta_usuario_id_created_at", "usuario_id", "created_at"),
        Index("ix_venta_created_at", "created_at"),
        # C-14 D11: todos los reportes filtran estado + rango de confirmada_at.
        Index("ix_venta_estado_confirmada_at", "estado", "confirmada_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    cliente_id = Column(
        String(36),
        ForeignKey("clientes.id"),
        nullable=True,
    )
    usuario_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=False,
    )
    estado = Column(
        Enum(*ESTADO_VENTA, name="estado_venta"),
        nullable=False,
        default="borrador",
        server_default="borrador",
    )
    total = Column(Numeric(12, 2), nullable=False)
    idempotency_key = Column(String(36), nullable=False)
    confirmada_at = Column(DateTime(timezone=True), nullable=True)
    confirmada_por_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=True,
    )
    anulada_at = Column(DateTime(timezone=True), nullable=True)
    anulada_por_id = Column(
        String(36),
        ForeignKey("usuarios.id"),
        nullable=True,
    )
    motivo_anulacion = Column(String, nullable=True)

    lineas = relationship(
        "LineaVenta",
        back_populates="venta",
        cascade="all, delete-orphan",
        order_by="LineaVenta.producto_id",
    )
    pagos = relationship(
        "PagoVenta",
        back_populates="venta",
        cascade="all, delete-orphan",
        order_by="(PagoVenta.created_at, PagoVenta.id)",
    )


class LineaVenta(Base):
    """Linea de una venta: producto, cantidad y precio congelado (D5).

    precio_unit/subtotal son snapshots inmutables (no derivados vivos);
    el invariante subtotal = cantidad x precio_unit lo garantiza el servicio
    (SQLite compara NUMERIC como float, un CHECK daria falsos rechazos, D2).
    Un producto por venta. Append-only como MovimientoStock.
    """

    __tablename__ = "linea_venta"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_linea_venta_cantidad_positiva"),
        CheckConstraint(
            "precio_unit > 0", name="ck_linea_venta_precio_unit_positivo"
        ),
        CheckConstraint("subtotal > 0", name="ck_linea_venta_subtotal_positivo"),
        CheckConstraint(
            "costo_unit IS NULL OR costo_unit > 0",
            name="ck_linea_venta_costo_unit_positivo",
        ),
        UniqueConstraint(
            "venta_id", "producto_id", name="uq_linea_venta_venta_producto"
        ),
        Index("ix_linea_venta_producto_id", "producto_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    venta_id = Column(
        String(36),
        ForeignKey("venta.id"),
        nullable=False,
    )
    producto_id = Column(
        String(36),
        ForeignKey("productos.id"),
        nullable=False,
    )
    cantidad = Column(Integer, nullable=False)
    precio_unit = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    # Costo del producto congelado junto con precio_unit al crear el borrador
    # (C-14 D1) para el margen historico. NULL en lineas previas a la 0008:
    # sin backfill, los reportes las informan aparte. Nunca sale por la API
    # de ventas.
    costo_unit = Column(Numeric(10, 2), nullable=True)

    venta = relationship("Venta", back_populates="lineas")
    producto = relationship("Producto")


@event.listens_for(LineaVenta, "before_update")
def _bloquear_update_linea_venta(mapper, connection, target) -> None:
    """Reject any UPDATE: las lineas de venta son insert-only (C-10 D2)."""
    raise InvalidRequestError("linea_venta es append-only: update bloqueado")


@event.listens_for(LineaVenta, "before_delete")
def _bloquear_delete_linea_venta(mapper, connection, target) -> None:
    """Reject any DELETE: las lineas de venta son insert-only (C-10 D2)."""
    raise InvalidRequestError("linea_venta es append-only: delete bloqueado")


class PagoVenta(Base):
    """Pago de una venta confirmada (C-10, D10, RN-VT-04).

    Varios por venta (mixto). ref_mp solo para metodo mp y unico en todo el
    sistema (un mismo pago MP no se acredita en dos ventas); los NULL no
    colisionan. Append-only: la anulacion de la venta no toca los pagos.
    """

    __tablename__ = "pago_venta"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_pago_venta_monto_positivo"),
        CheckConstraint(
            "ref_mp IS NULL OR metodo = 'mp'", name="ck_pago_venta_ref_mp_solo_mp"
        ),
        UniqueConstraint("ref_mp", name="uq_pago_venta_ref_mp"),
        Index("ix_pago_venta_venta_id", "venta_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    venta_id = Column(
        String(36),
        ForeignKey("venta.id"),
        nullable=False,
    )
    metodo = Column(
        Enum(*METODO_PAGO_VENTA, name="metodo_pago_venta"),
        nullable=False,
    )
    monto = Column(Numeric(12, 2), nullable=False)
    ref_mp = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    venta = relationship("Venta", back_populates="pagos")


@event.listens_for(PagoVenta, "before_update")
def _bloquear_update_pago_venta(mapper, connection, target) -> None:
    """Reject any UPDATE: los pagos de venta son insert-only (C-10 D2)."""
    raise InvalidRequestError("pago_venta es append-only: update bloqueado")


@event.listens_for(PagoVenta, "before_delete")
def _bloquear_delete_pago_venta(mapper, connection, target) -> None:
    """Reject any DELETE: los pagos de venta son insert-only (C-10 D2)."""
    raise InvalidRequestError("pago_venta es append-only: delete bloqueado")


class EventoOutbox(Base):
    """Bandeja de eventos transaccional (C-10 D11).

    Una fila por (tipo, agregado_id): `venta.confirmada` / `venta.anulada`
    con el id de la venta. Se inserta en la MISMA transaccion que la
    transicion (services/outbox.py), asi vive o muere con ella. Quedan
    pendientes (`procesado_at` nulo) hasta que un consumidor (C-11) los
    marque; el indice parcial acelera esa consulta de pendientes.
    """

    __tablename__ = "evento_outbox"
    __table_args__ = (
        UniqueConstraint(
            "tipo", "agregado_id", name="uq_evento_outbox_tipo_agregado"
        ),
        Index(
            "ix_evento_outbox_pendientes",
            "created_at",
            postgresql_where=text("procesado_at IS NULL"),
            sqlite_where=text("procesado_at IS NULL"),
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tipo = Column(String(50), nullable=False)
    agregado_id = Column(String(36), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    procesado_at = Column(DateTime(timezone=True), nullable=True)
