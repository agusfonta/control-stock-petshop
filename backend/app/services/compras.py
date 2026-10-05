"""Compras service: pedidos, recepcion, pagos y cuenta (C-07, D4).

Logica de negocio fuera del router: el servicio levanta errores de
dominio que el router mapea a HTTP (como ajustar_producto con StockError).
El stock solo se muta via services.stock.aplicar_movimiento (C-05 D1);
recibir_pedido es dueno de UNA transaccion para sus N movimientos (D3).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Distribuidora,
    EntradaStock,
    LineaPedido,
    ListaPrecio,
    PagoDistribuidora,
    PedidoCompra,
    Producto,
    Usuario,
)
from app.schemas import PagoCreate, PedidoCreate
from app.services.stock import aplicar_movimiento

__all__ = [
    "ComprasError",
    "NoEncontrado",
    "ReferenciaInactiva",
    "EstadoInvalido",
    "anular_pago",
    "cancelar_pedido",
    "crear_pedido",
    "cuenta_distribuidora",
    "obtener_pedido",
    "recibir_pedido",
    "registrar_pago",
    "total_pedido",
]


class ComprasError(Exception):
    """Base de errores de compras (el router los mapea a HTTP)."""


class NoEncontrado(ComprasError):
    """Distribuidora, producto, pedido o pago inexistente (mapea a 404)."""


class ReferenciaInactiva(ComprasError):
    """Distribuidora o producto dado de baja al crear un pedido (mapea a 422)."""


class EstadoInvalido(ComprasError):
    """Transicion no permitida desde el estado actual (mapea a 409)."""


def total_pedido(pedido: PedidoCompra) -> Decimal:
    """Total estimado: suma de cantidad x costo_unitario de las lineas."""
    subtotales = (
        Decimal(linea.cantidad) * Decimal(linea.costo_unitario)
        for linea in pedido.lineas
    )
    return sum(subtotales, Decimal(0))


def obtener_pedido(db: Session, pedido_id: str) -> PedidoCompra:
    """Pedido por id o NoEncontrado (lookup directo)."""
    pedido = db.get(PedidoCompra, pedido_id)
    if pedido is None:
        raise NoEncontrado("pedido no encontrado")
    return pedido


def crear_pedido(db: Session, data: PedidoCreate, usuario: Usuario) -> PedidoCompra:
    """Crea un pedido pendiente SIN tocar stock (RN-CP-02).

    El costo de cada linea es un snapshot (D6): el de la lista vigente de
    la distribuidora para ese producto (RN-CP-01) o, si no figura, el costo
    actual del producto. El cliente nunca envia costos. Ids inexistentes
    => NoEncontrado; distribuidora/producto inactivos => ReferenciaInactiva.
    """
    distribuidora = db.get(Distribuidora, data.distribuidora_id)
    if distribuidora is None:
        raise NoEncontrado("distribuidora no encontrada")
    if not distribuidora.activo:
        raise ReferenciaInactiva("distribuidora dada de baja")

    ids = [linea.producto_id for linea in data.lineas]
    productos = {
        p.id: p for p in db.query(Producto).filter(Producto.id.in_(ids)).all()
    }
    for producto_id in ids:
        producto = productos.get(producto_id)
        if producto is None:
            raise NoEncontrado(f"producto {producto_id} no encontrado")
        if not producto.activo:
            raise ReferenciaInactiva(f"producto {producto_id} dado de baja")

    costos_lista = {
        entrada.producto_id: entrada.costo
        for entrada in db.query(ListaPrecio).filter(
            ListaPrecio.distribuidora_id == distribuidora.id,
            ListaPrecio.producto_id.in_(ids),
            ListaPrecio.activo.is_(True),
        )
    }

    pedido = PedidoCompra(
        distribuidora_id=distribuidora.id,
        usuario_id=usuario.id,
        notas=data.notas,
    )
    for linea in data.lineas:
        pedido.lineas.append(
            LineaPedido(
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                costo_unitario=costos_lista.get(
                    linea.producto_id, productos[linea.producto_id].costo
                ),
            )
        )
    db.add(pedido)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(pedido)
    return pedido


def _bloquear_pedido(db: Session, pedido_id: str) -> PedidoCompra:
    """Pedido lockeado (FOR UPDATE salvo SQLite) o NoEncontrado (D7)."""
    query = db.query(PedidoCompra).filter(PedidoCompra.id == pedido_id)
    if db.bind is None or db.bind.dialect.name != "sqlite":
        query = query.with_for_update()
    pedido = query.one_or_none()
    if pedido is None:
        raise NoEncontrado("pedido no encontrado")
    return pedido


def _es_barrera_de_entrada(exc: IntegrityError) -> bool:
    """True si el IntegrityError es el unique (pedido_id, producto_id) de
    entrada_stock (doble recepcion, D7); False para cualquier otro."""
    return "entrada_stock" in str(exc.orig)


def recibir_pedido(db: Session, pedido_id: str, usuario: Usuario) -> PedidoCompra:
    """Recibe un pedido pendiente en UNA transaccion atomica (D3/D4/D5/D7).

    Lockea el pedido (FOR UPDATE salvo SQLite) y exige `pendiente`; por cada
    linea (ordenadas por producto_id: orden de lock determinista) crea la
    EntradaStock, aplica un movimiento `entrada` con ref_id a esa entrada y,
    si el costo difiere, copia el costo pactado al producto (D6; el
    precio_venta se recalcula solo, RN-PR-01). Un unico commit al final;
    ante cualquier fallo rollback total y re-raise. La actividad de
    distribuidora/productos no se revalida: la mercaderia ya llego (D11).
    """
    try:
        pedido = _bloquear_pedido(db, pedido_id)
        if pedido.estado != "pendiente":
            raise EstadoInvalido(f"el pedido esta {pedido.estado}, no pendiente")

        for linea in sorted(pedido.lineas, key=lambda li: li.producto_id):
            entrada = EntradaStock(
                id=str(uuid.uuid4()),
                pedido_id=pedido.id,
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                costo_unitario=linea.costo_unitario,
                usuario_id=usuario.id,
            )
            db.add(entrada)
            producto, _ = aplicar_movimiento(
                db,
                linea.producto_id,
                linea.cantidad,
                "entrada",
                usuario,
                motivo=f"recepcion pedido {pedido.id}",
                ref_id=entrada.id,
            )
            if producto.costo != linea.costo_unitario:
                producto.costo = linea.costo_unitario

        pedido.estado = "recibido"
        pedido.recibido_at = datetime.now(timezone.utc)
        pedido.recibido_por_id = usuario.id
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _es_barrera_de_entrada(exc):
            raise EstadoInvalido("el pedido ya fue recibido") from None
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(pedido)
    return pedido


def cancelar_pedido(db: Session, pedido_id: str) -> PedidoCompra:
    """Pasa un pedido pendiente a cancelado sin tocar stock ni costos.

    recibido y cancelado son estados finales: cualquier otro estado es
    EstadoInvalido (409). El pedido no se borra fisicamente (D2).
    """
    try:
        pedido = _bloquear_pedido(db, pedido_id)
        if pedido.estado != "pendiente":
            raise EstadoInvalido(f"el pedido esta {pedido.estado}, no pendiente")
        pedido.estado = "cancelado"
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(pedido)
    return pedido


def registrar_pago(
    db: Session, data: PagoCreate, usuario: Usuario
) -> PagoDistribuidora:
    """Registra un pago a una distribuidora (RN-CP-03, D9).

    Independiente de pedidos: no lee ni escribe pedidos, entradas ni stock.
    Admite distribuidoras inactivas (se puede saldar deuda con un proveedor
    dado de baja). fecha por defecto: hoy.
    """
    if db.get(Distribuidora, data.distribuidora_id) is None:
        raise NoEncontrado("distribuidora no encontrada")
    pago = PagoDistribuidora(
        distribuidora_id=data.distribuidora_id,
        monto=data.monto,
        metodo=data.metodo,
        fecha=data.fecha or date.today(),
        nota=data.nota,
        usuario_id=usuario.id,
    )
    db.add(pago)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(pago)
    return pago


def anular_pago(db: Session, pago_id: str) -> None:
    """Anula un pago por soft-delete (activo=False), nunca borrado fisico.

    Idempotente como los demas DELETE del proyecto: anular un pago ya
    anulado no falla. El pago anulado deja de listarse y de sumar (D9).
    """
    pago = db.get(PagoDistribuidora, pago_id)
    if pago is None:
        raise NoEncontrado("pago no encontrado")
    pago.activo = False
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


_CENTAVOS = Decimal("0.01")


def _a_decimal(valor: object) -> Decimal:
    """SUM de la base a Decimal con 2 decimales (None -> 0).

    SQLite devuelve float para NUMERIC; pasar por str evita arrastrar ruido
    binario y quantize fija los centavos. Postgres ya devuelve Decimal.
    """
    return Decimal(str(valor if valor is not None else 0)).quantize(_CENTAVOS)


def cuenta_distribuidora(
    db: Session, distribuidora_id: str
) -> tuple[Decimal, Decimal, Decimal]:
    """(total_recibido, total_pagado, saldo) calculado al vuelo (D10).

    total_recibido = SUM(cantidad x costo_unitario) de las entradas de
    pedidos recibidos de la distribuidora; total_pagado = SUM(monto) de sus
    pagos activos; saldo = recibido - pagado (positivo = deuda). Nada se
    persiste: sin columna saldo no hay drift.
    """
    if db.get(Distribuidora, distribuidora_id) is None:
        raise NoEncontrado("distribuidora no encontrada")
    recibido = (
        db.query(func.sum(EntradaStock.cantidad * EntradaStock.costo_unitario))
        .join(PedidoCompra, EntradaStock.pedido_id == PedidoCompra.id)
        .filter(
            PedidoCompra.distribuidora_id == distribuidora_id,
            PedidoCompra.estado == "recibido",
        )
        .scalar()
    )
    pagado = (
        db.query(func.sum(PagoDistribuidora.monto))
        .filter(
            PagoDistribuidora.distribuidora_id == distribuidora_id,
            PagoDistribuidora.activo.is_(True),
        )
        .scalar()
    )
    total_recibido = _a_decimal(recibido)
    total_pagado = _a_decimal(pagado)
    return total_recibido, total_pagado, total_recibido - total_pagado
