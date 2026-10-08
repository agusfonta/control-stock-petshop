"""Reportes de solo lectura: ventas del dia, mas vendidos, reposicion y margenes (C-14).

Servicio sin commit ni escrituras: agrega sobre ventas CONFIRMADAS y las
imputa al dia local del negocio (D4/D5). Los bordes del dia se calculan en
Python y se comparan como rango UTC contra `confirmada_at` (sin funciones de
zona en SQL: la misma consulta corre en Postgres y en SQLite y usa el indice
(estado, confirmada_at), D11). Las sumas de dinero que SQLite devuelve como
float se convierten via `str` y se redondean a centavos (D13).
"""

import math
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import LineaVenta, PagoVenta, Producto, Usuario, Venta
from app.schemas import (
    AnuladasResumen,
    MargenesQuery,
    MargenesResponse,
    MargenesTotales,
    MargenProducto,
    MasVendidosQuery,
    MasVendidosResponse,
    MetodoTotal,
    ProductoVendido,
    ReposicionItem,
    ReposicionQuery,
    ReposicionResponse,
    VentasDiaQuery,
    VentasDiaResponse,
)
from app.workers.stock_alerts import ids_bajo_minimo

__all__ = [
    "MAX_DIAS_PERIODO",
    "PERIODO_POR_DEFECTO_DIAS",
    "PeriodoInvalido",
    "bordes_utc",
    "cobertura_dias",
    "hoy",
    "margen_pct",
    "margenes",
    "mas_vendidos",
    "resolver_periodo",
    "ticket_promedio",
    "reposicion",
    "venta_diaria",
    "ventas_dia",
]

_CENTAVOS = Decimal("0.01")
_CUATRO_DECIMALES = Decimal("0.0001")
# Orden fijo de la respuesta de ventas del dia (D7): el consumidor no rellena huecos.
METODOS_DE_PAGO = ("efectivo", "transferencia", "mp", "tarjeta")
# Un anio, tambien bisiesto, contando ambos extremos (D6).
MAX_DIAS_PERIODO = 366
# Periodo por defecto: los ultimos 30 dias incluido hoy (D6).
PERIODO_POR_DEFECTO_DIAS = 30


class PeriodoInvalido(ValueError):
    """Periodo invertido o mas largo que el maximo (el router lo mapea a 422)."""


def _ahora_utc() -> datetime:
    """Instante actual en UTC; los tests lo reemplazan para fijar el reloj."""
    return datetime.now(timezone.utc)


def _zona() -> ZoneInfo:
    """Zona del negocio (REPORTES_TZ, ya validada al cargar settings)."""
    return ZoneInfo(get_settings().reportes_tz)


def hoy() -> date:
    """Fecha de hoy en la zona del negocio (no la fecha UTC, D5)."""
    return _ahora_utc().astimezone(_zona()).date()


def _inicio_del_dia_utc(dia: date) -> datetime:
    """Medianoche local de `dia` expresada en UTC."""
    return datetime.combine(dia, time.min, _zona()).astimezone(timezone.utc)


def bordes_utc(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """Rango UTC [inicio(desde), inicio(hasta + 1)) de un periodo de dias locales.

    Ambos extremos son dias completos e inclusivos; el borde superior es
    exclusivo, asi la medianoche local pertenece al dia nuevo (D5).
    """
    return _inicio_del_dia_utc(desde), _inicio_del_dia_utc(hasta + timedelta(days=1))


def resolver_periodo(desde: date | None, hasta: date | None) -> tuple[date, date]:
    """Completa y valida un periodo `desde`/`hasta` (D6).

    Sin bordes: los ultimos 30 dias con hoy; solo `desde`: hasta hoy; solo
    `hasta`: 29 dias antes. `desde > hasta` o mas de 366 dias levanta
    PeriodoInvalido. Las fechas futuras se aceptan (dan reportes vacios).
    """
    if hasta is None:
        hasta = hoy()
    if desde is None:
        desde = hasta - timedelta(days=PERIODO_POR_DEFECTO_DIAS - 1)
    if desde > hasta:
        raise PeriodoInvalido("desde no puede ser posterior a hasta")
    if (hasta - desde).days + 1 > MAX_DIAS_PERIODO:
        raise PeriodoInvalido(f"el periodo no puede superar {MAX_DIAS_PERIODO} dias")
    return desde, hasta


def ticket_promedio(total: Decimal, cantidad: int) -> Decimal:
    """total / cantidad a centavos, mitad hacia arriba; 0 sin ventas (D7)."""
    if cantidad == 0:
        return Decimal(0).quantize(_CENTAVOS)
    return (total / cantidad).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def venta_diaria(unidades: int, dias: int) -> Decimal:
    """Unidades vendidas por dia de la ventana, a centavos mitad arriba (D9)."""
    return (Decimal(unidades) / dias).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def cobertura_dias(stock_actual: int, unidades: int, dias: int) -> int | None:
    """Dias que alcanza el stock al ritmo de la ventana, o None sin ventas (D9).

    floor(stock x dias / unidades) con enteros: no pasa por venta_diaria
    redondeada y trunca (1,9 dias se informa como 1, conservador).
    """
    if unidades == 0:
        return None
    return (stock_actual * dias) // unidades


def margen_pct(margen_bruto: Decimal, costo: Decimal) -> Decimal | None:
    """margen_bruto / costo con 4 decimales mitad arriba; None si costo es 0 (D10).

    Markup sobre costo, el mismo sentido que Producto.margen_pct (RN-PR-01).
    """
    if costo == 0:
        return None
    return (margen_bruto / costo).quantize(_CUATRO_DECIMALES, rounding=ROUND_HALF_UP)


def _dinero(valor: object) -> Decimal:
    """Suma de dinero a Decimal con centavos (mitad arriba), 0 si no hay filas.

    SQLite devuelve las sumas de NUMERIC como float: se pasa por `str` y se
    redondea para no arrastrar ruido binario (D13). En Postgres ya es Decimal.
    """
    if valor is None:
        return Decimal(0).quantize(_CENTAVOS)
    return Decimal(str(valor)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def _es_duena(usuario: Usuario) -> bool:
    return str(usuario.rol) == "duena"


def _filtro_ventas(
    estado: str, inicio: datetime, fin: datetime, usuario: Usuario | None
) -> list:
    """Criterio unico de "que venta cuenta y en que dia" (D4/D5).

    Estado exacto + `confirmada_at` en [inicio, fin) UTC; el mostrador queda
    restringido a las ventas de las que es vendedor (D12). Con `usuario=None`
    no se restringe por vendedor (rotacion de stock: es del negocio).
    """
    condiciones = [
        Venta.estado == estado,
        Venta.confirmada_at >= inicio,
        Venta.confirmada_at < fin,
    ]
    if usuario is not None and not _es_duena(usuario):
        condiciones.append(Venta.usuario_id == usuario.id)
    return condiciones


def ventas_dia(
    db: Session, query: VentasDiaQuery, usuario: Usuario
) -> VentasDiaResponse:
    """Ventas confirmadas del dia local, por metodo, y anuladas aparte (D7).

    Cuatro agregados simples con el mismo filtro base: ventas (cantidad y
    total), lineas (unidades), pagos por metodo y anuladas del dia.
    """
    dia = query.fecha
    inicio, fin = bordes_utc(dia, dia)
    confirmadas = _filtro_ventas("confirmada", inicio, fin, usuario)

    cantidad_ventas, total = db.query(
        func.count(Venta.id), func.sum(Venta.total)
    ).filter(*confirmadas).one()
    unidades = (
        db.query(func.sum(LineaVenta.cantidad))
        .join(Venta, LineaVenta.venta_id == Venta.id)
        .filter(*confirmadas)
        .scalar()
    )
    pagos = {
        str(metodo): (monto, cantidad)
        for metodo, monto, cantidad in db.query(
            PagoVenta.metodo, func.sum(PagoVenta.monto), func.count(PagoVenta.id)
        )
        .join(Venta, PagoVenta.venta_id == Venta.id)
        .filter(*confirmadas)
        .group_by(PagoVenta.metodo)
        .all()
    }
    cantidad_anuladas, total_anuladas = db.query(
        func.count(Venta.id), func.sum(Venta.total)
    ).filter(*_filtro_ventas("anulada", inicio, fin, usuario)).one()

    total_vendido = _dinero(total)
    return VentasDiaResponse(
        fecha=dia,
        alcance="todas" if _es_duena(usuario) else "propias",
        cantidad_ventas=cantidad_ventas,
        total_vendido=total_vendido,
        ticket_promedio=ticket_promedio(total_vendido, cantidad_ventas),
        unidades_vendidas=int(unidades or 0),
        por_metodo=[
            MetodoTotal(
                metodo=metodo,
                monto=_dinero(pagos.get(metodo, (None, 0))[0]),
                cantidad_pagos=pagos.get(metodo, (None, 0))[1],
            )
            for metodo in METODOS_DE_PAGO
        ],
        anuladas=AnuladasResumen(
            cantidad=cantidad_anuladas, total=_dinero(total_anuladas)
        ),
    )


def mas_vendidos(
    db: Session, query: MasVendidosQuery, usuario: Usuario
) -> MasVendidosResponse:
    """Ranking top-N de productos del periodo por unidades o monto (D8).

    Agrupa por producto las lineas de ventas confirmadas del periodo (incluye
    productos dados de baja: vendieron, ocultarlos falsearia el ranking). El
    orden es descendente por la metrica elegida, luego por la otra y luego
    por producto_id; se aplica en Python sobre Decimal exactos (un fila por
    producto vendido, acotado por el catalogo) para que el desempate no
    dependa de las sumas float de SQLite ni de la collation del motor.
    """
    inicio, fin = bordes_utc(query.desde, query.hasta)
    filas = (
        db.query(
            Producto.id,
            Producto.sku,
            Producto.nombre,
            Producto.activo,
            func.sum(LineaVenta.cantidad),
            func.sum(LineaVenta.subtotal),
        )
        .join(LineaVenta, LineaVenta.producto_id == Producto.id)
        .join(Venta, LineaVenta.venta_id == Venta.id)
        .filter(*_filtro_ventas("confirmada", inicio, fin, usuario))
        .group_by(Producto.id, Producto.sku, Producto.nombre, Producto.activo)
        .all()
    )
    productos = [
        ProductoVendido(
            producto_id=producto_id,
            sku=sku,
            nombre=nombre,
            activo=bool(activo),
            unidades=int(unidades),
            monto=_dinero(monto),
        )
        for producto_id, sku, nombre, activo, unidades, monto in filas
    ]
    if query.orden == "cantidad":
        def clave(p: ProductoVendido):
            return (-p.unidades, -p.monto, p.producto_id)
    else:
        def clave(p: ProductoVendido):
            return (-p.monto, -p.unidades, p.producto_id)
    productos.sort(key=clave)
    return MasVendidosResponse(
        desde=query.desde,
        hasta=query.hasta,
        orden=query.orden,
        items=productos[: query.limite],
    )


def reposicion(db: Session, query: ReposicionQuery) -> ReposicionResponse:
    """Productos activos a reponer: bajo minimo o con cobertura corta (D9).

    La rotacion sale de las lineas de ventas confirmadas de la ventana (los
    ultimos `dias` dias locales con hoy), de todo el negocio y no del
    vendedor: la anulacion no cuenta sin restar signos. "Bajo minimo" reutiliza
    `ids_bajo_minimo` de las alertas de C-05 para que ambas listas coincidan
    por construccion. Orden: cobertura ascendente con None al final, luego
    holgura sobre el minimo y producto_id.
    """
    dias = query.dias
    hasta = hoy()
    inicio, fin = bordes_utc(hasta - timedelta(days=dias - 1), hasta)
    rotacion = {
        producto_id: int(unidades)
        for producto_id, unidades in db.query(
            LineaVenta.producto_id, func.sum(LineaVenta.cantidad)
        )
        .join(Venta, LineaVenta.venta_id == Venta.id)
        .filter(*_filtro_ventas("confirmada", inicio, fin, None))
        .group_by(LineaVenta.producto_id)
        .all()
    }
    bajo_minimo = set(ids_bajo_minimo(db))

    items = []
    for producto in db.query(Producto).filter(Producto.activo.is_(True)).all():
        unidades = rotacion.get(producto.id, 0)
        cobertura = cobertura_dias(producto.stock_actual, unidades, dias)
        es_bajo_minimo = producto.id in bajo_minimo
        if not es_bajo_minimo and (
            cobertura is None or cobertura > query.cobertura_max_dias
        ):
            continue
        items.append(
            ReposicionItem(
                producto_id=producto.id,
                sku=producto.sku,
                nombre=producto.nombre,
                stock_actual=producto.stock_actual,
                stock_minimo=producto.stock_minimo,
                bajo_minimo=es_bajo_minimo,
                unidades_vendidas=unidades,
                venta_diaria=venta_diaria(unidades, dias),
                cobertura_dias=cobertura,
                distribuidora_default_id=producto.distribuidora_default_id,
            )
        )
    items.sort(
        key=lambda i: (
            i.cobertura_dias is None,
            i.cobertura_dias or 0,
            i.stock_actual - i.stock_minimo,
            i.producto_id,
        )
    )
    return ReposicionResponse(
        dias=dias, cobertura_max_dias=query.cobertura_max_dias, items=items
    )


def margenes(db: Session, query: MargenesQuery) -> MargenesResponse:
    """Margen por producto y total del periodo con el costo congelado (D1/D10).

    Solo cuentan las lineas de ventas confirmadas que tienen `costo_unit`:
    ingresos = sum(subtotal), costo = sum(cantidad x costo_unit). Las lineas
    sin costo (previas a la migracion 0008) no entran en ningun producto ni
    total: se informan aparte en `lineas_sin_costo`/`ingresos_sin_costo`. Los
    totales cubren todo el periodo, no la pagina. Como los importes de las
    lineas ya tienen centavos, sumar las filas por producto es exacto; el
    orden (margen_bruto desc, producto_id) y la paginacion se aplican en
    Python sobre Decimal para no depender de las sumas float de SQLite.
    """
    inicio, fin = bordes_utc(query.desde, query.hasta)
    periodo = _filtro_ventas("confirmada", inicio, fin, None)

    filas = (
        db.query(
            Producto.id,
            Producto.sku,
            Producto.nombre,
            func.sum(LineaVenta.cantidad),
            func.sum(LineaVenta.subtotal),
            func.sum(LineaVenta.cantidad * LineaVenta.costo_unit),
        )
        .join(LineaVenta, LineaVenta.producto_id == Producto.id)
        .join(Venta, LineaVenta.venta_id == Venta.id)
        .filter(*periodo, LineaVenta.costo_unit.is_not(None))
        .group_by(Producto.id, Producto.sku, Producto.nombre)
        .all()
    )
    productos = []
    for producto_id, sku, nombre, unidades, ingresos, costo in filas:
        ingresos, costo = _dinero(ingresos), _dinero(costo)
        productos.append(
            MargenProducto(
                producto_id=producto_id,
                sku=sku,
                nombre=nombre,
                unidades=int(unidades),
                ingresos=ingresos,
                costo=costo,
                margen_bruto=ingresos - costo,
                margen_pct=margen_pct(ingresos - costo, costo),
            )
        )
    productos.sort(key=lambda p: (-p.margen_bruto, p.producto_id))

    sin_costo, ingresos_sin_costo = (
        db.query(func.count(LineaVenta.id), func.sum(LineaVenta.subtotal))
        .join(Venta, LineaVenta.venta_id == Venta.id)
        .filter(*periodo, LineaVenta.costo_unit.is_(None))
        .one()
    )
    ingresos = sum((p.ingresos for p in productos), Decimal(0)).quantize(_CENTAVOS)
    costo = sum((p.costo for p in productos), Decimal(0)).quantize(_CENTAVOS)
    total = len(productos)
    desde_fila = (query.page - 1) * query.page_size
    return MargenesResponse(
        desde=query.desde,
        hasta=query.hasta,
        totales=MargenesTotales(
            ingresos=ingresos,
            costo=costo,
            margen_bruto=ingresos - costo,
            margen_pct=margen_pct(ingresos - costo, costo),
            lineas_sin_costo=sin_costo,
            ingresos_sin_costo=_dinero(ingresos_sin_costo),
        ),
        total=total,
        page=query.page,
        page_size=query.page_size,
        total_pages=math.ceil(total / query.page_size) if total else 0,
        items=productos[desde_fila : desde_fila + query.page_size],
    )
