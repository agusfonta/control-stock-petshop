"""Modelos de compras: pedidos, lineas, entradas y pagos."""

from datetime import date

from sqlalchemy import (
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
)
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import relationship

from app.core.base import AuditMixin, _uuid
from app.core.db import Base

ESTADO_PEDIDO = ("pendiente", "recibido", "cancelado")


METODO_PAGO_DISTRIBUIDORA = ("efectivo", "transferencia", "cheque", "otro")


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
