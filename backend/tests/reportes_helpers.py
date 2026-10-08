"""Helpers compartidos por los tests de reportes (C-14). No es un modulo de tests.

Reutiliza ventas_helpers (crear/confirmar/anular por la API) y agrega lo que
los reportes necesitan: fijar el instante de confirmacion de una venta (UPDATE
directo de `venta`, que no es append-only), fijar el reloj de `hoy()` y armar
ventas confirmadas "con historia" sin pasar por la API.
"""

import uuid
from datetime import datetime, timezone

from tests.ventas_helpers import (  # noqa: F401  (re-export para los tests)
    CLIENTES_URL,
    VENTAS_URL,
    clave_nueva,
    contar,
    crear_cliente,
    crear_producto,
    crear_venta,
    get_producto,
    get_venta,
    login_duena,
    login_mostrador,
    movimientos_de,
    pago,
    post_anular,
    post_confirmar,
    post_venta,
    usuario_id,
    venta_confirmada,
)

REPORTES_URL = "/api/reportes"


def utc(*args) -> datetime:
    """datetime aware en UTC: utc(2026, 10, 6, 2, 30)."""
    return datetime(*args, tzinfo=timezone.utc)


def fijar_ahora(monkeypatch, instante_utc: datetime) -> None:
    """Fija el reloj del servicio de reportes: hoy() se deriva de este instante."""
    from app.services import reportes

    monkeypatch.setattr(reportes, "_ahora_utc", lambda: instante_utc)


def fijar_confirmada_at(db_session_factory, venta_id: str, instante_utc: datetime) -> None:
    """Mueve la confirmacion de una venta a `instante_utc` (UPDATE directo)."""
    from sqlalchemy import update

    from app.models import Venta

    with db_session_factory() as session:
        session.execute(
            update(Venta).where(Venta.id == venta_id).values(confirmada_at=instante_utc)
        )
        session.commit()


async def venta_confirmada_en(
    client,
    headers,
    db_session_factory,
    lineas,
    pagos,
    instante_utc: datetime,
    **kwargs,
) -> dict:
    """Venta confirmada por la API cuya confirmacion se imputa a `instante_utc`."""
    venta = await venta_confirmada(client, headers, lineas, pagos, **kwargs)
    fijar_confirmada_at(db_session_factory, venta["id"], instante_utc)
    return venta


async def get_reporte(client, headers, nombre: str, **params):
    """GET crudo de un reporte (devuelve la response)."""
    return await client.get(f"{REPORTES_URL}/{nombre}", params=params, headers=headers)


def insertar_venta_confirmada(
    db_session_factory,
    usuario_id_: str,
    lineas: list[tuple[str, int, object, object]],
    confirmada_at: datetime,
    metodo: str = "efectivo",
) -> str:
    """Inserta por sesion una venta confirmada con su pago, sin tocar stock.

    `lineas` es [(producto_id, cantidad, precio_unit, costo_unit)]; un
    `costo_unit` None deja la linea sin costo congelado (como las previas a la
    migracion 0008, que la API ya no puede producir).
    """
    from decimal import Decimal

    from app.models import LineaVenta, PagoVenta, Venta

    total = sum((Decimal(str(c)) * Decimal(str(p)) for _, c, p, _ in lineas), Decimal(0))
    with db_session_factory() as session:
        venta = Venta(
            usuario_id=usuario_id_,
            idempotency_key=str(uuid.uuid4()),
            estado="confirmada",
            total=total,
            confirmada_at=confirmada_at,
            confirmada_por_id=usuario_id_,
        )
        for producto_id, cantidad, precio, costo in lineas:
            venta.lineas.append(
                LineaVenta(
                    producto_id=producto_id,
                    cantidad=cantidad,
                    precio_unit=Decimal(str(precio)),
                    subtotal=Decimal(str(precio)) * cantidad,
                    costo_unit=None if costo is None else Decimal(str(costo)),
                )
            )
        venta.pagos.append(PagoVenta(metodo=metodo, monto=total))
        session.add(venta)
        session.commit()
        return venta.id
