"""Stock service: unica via de mutacion de existencias (C-05, decision D1).

Toda mutacion de stock_actual ocurre junto a su MovimientoStock en la
misma transaccion (RN-ST-03). C-07/C-10 reutilizan ajustar() para
entradas y ventas. SELECT FOR UPDATE en Postgres evita el race de
dos ajustes concurrentes sobre el mismo stock_previo.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import MovimientoStock, Producto, Usuario

__all__ = [
    "StockError",
    "ProductoNoEncontrado",
    "MotivoInvalido",
    "StockNegativo",
    "ajustar",
]


class StockError(Exception):
    """Base de errores de stock (el router los mapea a HTTP)."""


class ProductoNoEncontrado(StockError):
    """El producto a ajustar no existe (mapea a 404)."""


class MotivoInvalido(StockError):
    """Motivo ausente o vacio: sin motivo no hay trazabilidad (mapea a 422)."""


class StockNegativo(StockError):
    """El delta dejaria stock_nuevo < 0 (mapea a 422)."""


def ajustar(
    db: Session,
    producto_id: str,
    cantidad_delta: int,
    motivo: str,
    usuario: Usuario,
    tipo: str = "ajuste",
) -> tuple[Producto, MovimientoStock]:
    """Aplica cantidad_delta al stock y crea su movimiento en 1 transaccion.

    Lock pesimista de la fila (FOR UPDATE salvo en SQLite, que no lo
    soporta y serializa el writer de todos modos). Rollback total ante
    cualquier fallo: nunca queda stock a medias sin su movimiento.
    """
    motivo_limpio = (motivo or "").strip()
    if not motivo_limpio:
        raise MotivoInvalido("motivo obligatorio no vacio")
    if cantidad_delta == 0:
        raise StockError("cantidad_delta no puede ser 0")

    query = db.query(Producto).filter(Producto.id == producto_id)
    if db.bind is None or db.bind.dialect.name != "sqlite":
        query = query.with_for_update()
    producto = query.one_or_none()
    if producto is None:
        raise ProductoNoEncontrado(f"producto {producto_id} no encontrado")

    stock_previo = producto.stock_actual
    stock_nuevo = stock_previo + cantidad_delta
    if stock_nuevo < 0:
        raise StockNegativo(
            f"stock_nuevo {stock_nuevo} < 0 (previo {stock_previo}, "
            f"delta {cantidad_delta})"
        )

    producto.stock_actual = stock_nuevo
    movimiento = MovimientoStock(
        producto_id=producto.id,
        tipo=tipo,
        cantidad=cantidad_delta,
        stock_previo=stock_previo,
        stock_nuevo=stock_nuevo,
        motivo=motivo_limpio,
        usuario_id=usuario.id,
    )
    db.add(movimiento)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise StockNegativo("la base rechazo el movimiento (check)") from None
    except Exception:
        db.rollback()
        raise
    db.refresh(producto)
    db.refresh(movimiento)
    return producto, movimiento
