"""Job de alertas de bajo minimo (C-05, Flujo 2 de reposicion).

Recalcula el SET `stock:bajo_minimo` con los ids de productos activos
bajo minimo y TTL corto (env STOCK_ALERT_TTL_S, default 60s). El job
nunca escribe stock: solo el conjunto de alerta. Si Redis cae, el
endpoint degrada a computo directo (el job propaga la excepcion para
que el scheduler la vea y reintente).

Uso en prod (cron/worker existente):
    from app.workers.stock_alerts import recalcular_alertas
    recalcular_alertas(db, redis_client, ttl_s=settings.stock_alert_ttl_s)
"""

import redis as redis_lib
from sqlalchemy.orm import Session

from app.models import Producto

__all__ = ["ALERTAS_KEY", "ids_bajo_minimo", "recalcular_alertas"]

ALERTAS_KEY = "stock:bajo_minimo"


def ids_bajo_minimo(db: Session) -> list[str]:
    """Ids de productos activos con stock_actual <= stock_minimo."""
    rows = (
        db.query(Producto.id)
        .filter(
            Producto.activo.is_(True),
            Producto.stock_actual <= Producto.stock_minimo,
        )
        .all()
    )
    return [row[0] for row in rows]


def recalcular_alertas(
    db: Session, cache: redis_lib.Redis, ttl_s: int = 60
) -> list[str]:
    """Reescribe el SET de alerta con TTL y devuelve los ids incluidos."""
    ids = ids_bajo_minimo(db)
    pipe = cache.pipeline()
    pipe.delete(ALERTAS_KEY)
    if ids:
        pipe.sadd(ALERTAS_KEY, *ids)
    pipe.expire(ALERTAS_KEY, ttl_s)
    pipe.execute()
    return ids
