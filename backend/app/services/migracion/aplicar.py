"""Aplicacion del `Plan` en una sola transaccion (C-08, D4/D5/D6).

Todo-o-nada: distribuidoras -> productos (nuevos y actualizados) -> movimientos
de apertura -> un unico commit. Cualquier falla revierte el lote completo.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Distribuidora, Producto, Usuario
from app.services.migracion.analisis import FilaPlan, Plan
from app.services.migracion.normalizar import clave
from app.services.stock import aplicar_movimiento

CAMPOS_PRODUCTO = ("nombre", "categoria", "marca", "unidad", "costo", "margen_pct", "stock_minimo")


class CatalogoCambio(Exception):
    """El catalogo cambio entre el analisis y la aplicacion (se traduce a 409)."""


def _crear_distribuidoras(db: Session, plan: Plan) -> dict[str, str]:
    """clave(nombre) -> id de cada distribuidora nueva (una por nombre)."""
    ids: dict[str, str] = {}
    for nombre in plan.distribuidoras_a_crear:
        dist = Distribuidora(nombre=nombre)
        db.add(dist)
        db.flush()
        ids[clave(nombre)] = dist.id
    return ids


def _distribuidora_id(fila: FilaPlan, nuevas: dict[str, str]) -> str | None:
    nueva = fila.valores.get("distribuidora_nueva")
    if nueva:
        return nuevas[clave(nueva)]
    return fila.valores.get("distribuidora_id")


def _crear_producto(db: Session, fila: FilaPlan, nuevas: dict[str, str]) -> Producto:
    v = fila.valores
    producto = Producto(
        sku=fila.sku,
        stock_actual=0,  # el stock entra por el movimiento de apertura (RN-ST-03)
        distribuidora_default_id=_distribuidora_id(fila, nuevas),
        **{campo: v[campo] for campo in CAMPOS_PRODUCTO},
    )
    db.add(producto)
    db.flush()
    return producto


def _actualizar_producto(db: Session, fila: FilaPlan, nuevas: dict[str, str]) -> None:
    producto = db.get(Producto, fila.producto_id)
    for campo in fila.campos_cambiados:
        if campo == "distribuidora":
            producto.distribuidora_default_id = _distribuidora_id(fila, nuevas)
        else:
            setattr(producto, campo, fila.valores[campo])
    db.flush()


def _aplicar(
    db: Session, plan: Plan, usuario: Usuario, nombre_archivo: str, lote_id: str
) -> None:
    nuevas = _crear_distribuidoras(db, plan)
    for fila in plan.filas:
        if fila.accion == "crear":
            producto = _crear_producto(db, fila, nuevas)
            stock = fila.valores.get("stock_inicial") or 0
            if stock > 0:
                aplicar_movimiento(
                    db, producto.id, stock, "apertura", usuario,
                    motivo=f"Migración inicial: {nombre_archivo}", ref_id=lote_id,
                )
        elif fila.accion == "actualizar":
            _actualizar_producto(db, fila, nuevas)


def aplicar(
    db: Session, plan: Plan, usuario: Usuario, nombre_archivo: str, lote_id: str
) -> None:
    """Escribe el plan completo o nada: rollback total ante cualquier falla."""
    try:
        _aplicar(db, plan, usuario, nombre_archivo, lote_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CatalogoCambio(
            "el catalogo cambio durante la importacion (por ejemplo, un SKU creado "
            "en paralelo); volve a analizar el archivo"
        ) from exc
    except Exception:
        db.rollback()
        raise
