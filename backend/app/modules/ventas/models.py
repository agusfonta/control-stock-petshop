"""Modelos de ventas: venta, lineas y pagos."""


from sqlalchemy import (
    CheckConstraint,
    Column,
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
)
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import relationship

from app.core.base import AuditMixin, _uuid
from app.core.db import Base

ESTADO_VENTA = ("borrador", "confirmada", "anulada")


METODO_PAGO_VENTA = ("efectivo", "transferencia", "mp", "tarjeta")


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
