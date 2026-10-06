"""Ventas service: borrador, confirmacion, anulacion y lecturas (C-10, D16).

Logica de negocio fuera del router: el servicio levanta errores de dominio
que el router mapea a HTTP (como compras). El stock solo se muta via
services.stock.aplicar_movimiento (C-05 D1, sin modificarlo); confirmar y
anular son duenos de UNA transaccion para sus N movimientos (D6). Los
eventos de facturacion van por el outbox en esa misma transaccion (D11).
"""

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Cliente, LineaVenta, PagoVenta, Producto, Usuario, Venta
from app.schemas import (
    AnularVentaRequest,
    ConfirmarVentaRequest,
    LineaVentaIn,
    PagoVentaIn,
    VentaCreate,
    VentaFiltros,
)
from app.services.outbox import registrar_evento
from app.services.stock import StockNegativo, aplicar_movimiento

__all__ = [
    "VentasError",
    "NoEncontrado",
    "ReferenciaInactiva",
    "IdempotenciaConflicto",
    "PagosInvalidos",
    "StockInsuficiente",
    "EstadoInvalido",
    "RefMpDuplicada",
    "anular_venta",
    "confirmar_venta",
    "crear_venta",
    "listar_ventas",
    "obtener_venta",
    "ventas_de_cliente",
]

_CENTAVOS = Decimal("0.01")
# Sin filtro de estado el listado excluye los borradores (D15).
ESTADOS_LISTADO = ("confirmada", "anulada")


class VentasError(Exception):
    """Base de errores de ventas (el router los mapea a HTTP)."""


class NoEncontrado(VentasError):
    """Venta, producto o cliente inexistente (mapea a 404)."""


class ReferenciaInactiva(VentasError):
    """Producto o cliente dado de baja al crear un borrador (mapea a 422)."""


class IdempotenciaConflicto(VentasError):
    """Misma idempotency_key del mismo usuario con otro contenido (422, D8)."""


class PagosInvalidos(VentasError):
    """Pagos que no igualan el total o con ref_mp en otro metodo (422, RN-VT-04)."""


class EstadoInvalido(VentasError):
    """Transicion no permitida desde el estado actual (mapea a 409, D9)."""


class RefMpDuplicada(VentasError):
    """ref_mp ya registrado en otro pago del sistema (mapea a 409, D10)."""


class StockInsuficiente(VentasError):
    """Alguna linea supera el stock disponible (409, RN-VT-01, D7).

    `faltantes` lista, por cada linea faltante, producto_id, solicitado y
    disponible, para que el POS sugiera bajar a lo disponible.
    """

    def __init__(self, faltantes: list[dict]) -> None:
        super().__init__("stock insuficiente")
        self.faltantes = faltantes


def _precio_unitario(producto: Producto) -> Decimal:
    """precio_venta (costo x (1 + margen), RN-PR-01) a centavos, mitad arriba.

    Se calcula en Decimal desde costo y margen_pct en vez de leer la
    column_property: SQLite la devuelve redondeada a 4 decimales (doble
    redondeo) mientras Postgres la devuelve exacta; asi el resultado es el
    mismo en ambos y se redondea UNA sola vez (D5).
    """
    costo = Decimal(str(producto.costo))
    margen = Decimal(str(producto.margen_pct))
    return (costo * (1 + margen)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def _buscar_por_clave(db: Session, usuario_id: str, clave: str) -> Venta | None:
    """Venta del usuario con esa idempotency_key (D8), o None."""
    return (
        db.query(Venta)
        .filter(Venta.usuario_id == usuario_id, Venta.idempotency_key == clave)
        .one_or_none()
    )


def _mismo_contenido(venta: Venta, data: VentaCreate) -> bool:
    """Mismo cliente y mismo conjunto (producto, cantidad) que la venta (D8)."""
    pedido = {linea.producto_id: linea.cantidad for linea in data.lineas}
    existente = {linea.producto_id: linea.cantidad for linea in venta.lineas}
    return venta.cliente_id == data.cliente_id and pedido == existente


def _resolver_replay(venta: Venta, data: VentaCreate) -> Venta:
    """Replay (mismo contenido) o IdempotenciaConflicto (otro contenido)."""
    if not _mismo_contenido(venta, data):
        raise IdempotenciaConflicto(
            "idempotency_key ya usada con otro contenido"
        )
    return venta


def crear_venta(
    db: Session, data: VentaCreate, usuario: Usuario
) -> tuple[Venta, bool]:
    """Crea un borrador SIN tocar stock; devuelve (venta, creada).

    Idempotente por (usuario, idempotency_key) (D8): la misma clave con el
    mismo contenido devuelve la venta existente en su estado actual
    (creada=False) sin re-validar stock ni re-cotizar; con otro contenido
    levanta IdempotenciaConflicto. Precio, subtotal y total los fija el
    servidor (D5). Valida referencias (404/422, D16) y stock temprano sin
    lock (D7: la garantia real es la revalidacion al confirmar). Un solo
    commit; la carrera de dos altas simultaneas con la misma clave se
    resuelve por el unique y se trata como replay o conflicto, nunca 500.
    """
    existente = _buscar_por_clave(db, usuario.id, data.idempotency_key)
    if existente is not None:
        return _resolver_replay(existente, data), False

    if data.cliente_id is not None:
        cliente = db.get(Cliente, data.cliente_id)
        if cliente is None:
            raise NoEncontrado("cliente no encontrado")
        if not cliente.activo:
            raise ReferenciaInactiva("cliente dado de baja")

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

    faltantes = _faltantes(data.lineas, productos)
    if faltantes:
        raise StockInsuficiente(faltantes)

    venta = Venta(
        cliente_id=data.cliente_id,
        usuario_id=usuario.id,
        idempotency_key=data.idempotency_key,
        total=Decimal(0),
    )
    total = Decimal(0)
    for linea in data.lineas:
        precio_unit = _precio_unitario(productos[linea.producto_id])
        subtotal = precio_unit * linea.cantidad
        total += subtotal
        venta.lineas.append(
            LineaVenta(
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                precio_unit=precio_unit,
                subtotal=subtotal,
            )
        )
    venta.total = total
    db.add(venta)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Carrera por la clave: la otra request gano el unique (D8).
        ganadora = _buscar_por_clave(db, usuario.id, data.idempotency_key)
        if ganadora is None:
            raise
        return _resolver_replay(ganadora, data), False
    db.refresh(venta)
    return venta, True


def _validar_pagos(venta: Venta, pagos: list[PagoVentaIn]) -> None:
    """Pagos contra el total inmutable de la venta (RN-VT-04, D10).

    Suma exacta en Decimal; ref_mp solo con metodo mp. Se valida ANTES de
    tocar nada: un incumplimiento no escribe ni lockea.
    """
    for pago in pagos:
        if pago.ref_mp is not None and pago.metodo != "mp":
            raise PagosInvalidos("ref_mp solo se admite en pagos mp")
    suma = sum((pago.monto for pago in pagos), Decimal(0))
    total = Decimal(str(venta.total))
    if suma != total:
        raise PagosInvalidos(f"los pagos suman {suma} y el total es {total}")


def _firma_pagos(pagos: list[tuple[str, object, str | None]]) -> Counter:
    """Multiconjunto (metodo, monto a centavos, ref_mp) para comparar pagos."""
    return Counter(
        (str(metodo), Decimal(str(monto)).quantize(_CENTAVOS), ref_mp)
        for metodo, monto, ref_mp in pagos
    )


def _faltantes(
    lineas: Sequence[LineaVenta | LineaVentaIn], productos: dict[str, Producto]
) -> list[dict]:
    """Lineas cuya cantidad supera el stock actual (D7), en orden de linea.

    Sirve tanto para las lineas del request (borrador, chequeo temprano) como
    para las persistidas (confirmacion, ya con los productos lockeados).
    """
    return [
        {
            "producto_id": linea.producto_id,
            "solicitado": linea.cantidad,
            "disponible": productos[linea.producto_id].stock_actual,
        }
        for linea in lineas
        if linea.cantidad > productos[linea.producto_id].stock_actual
    ]


def _bloquear_productos(db: Session, producto_ids: list[str]) -> dict[str, Producto]:
    """Productos de la venta lockeados en UNA consulta ORDER BY id (D6.3).

    FOR UPDATE salvo SQLite (que no lo soporta y serializa el writer). El
    orden por id es el mismo de C-07: sin ciclos de deadlock entre ventas,
    recepciones y ajustes. populate_existing refresca el stock leido.
    """
    query = (
        db.query(Producto)
        .filter(Producto.id.in_(producto_ids))
        .order_by(Producto.id)
        .populate_existing()
    )
    if db.bind is None or db.bind.dialect.name != "sqlite":
        query = query.with_for_update()
    return {producto.id: producto for producto in query.all()}


def _es_duena(usuario: Usuario) -> bool:
    return str(usuario.rol) == "duena"


def _cargar_venta(db: Session, venta_id: str, usuario: Usuario) -> Venta:
    """Venta por id o NoEncontrado; una venta ajena no existe para el mostrador.

    D12: la duena opera sobre cualquier venta; un mostrador solo sobre las
    que creo (usuario_id), y la ajena responde 404 (no 403) para no revelar
    que existe.
    """
    venta = db.get(Venta, venta_id)
    if venta is None or (not _es_duena(usuario) and venta.usuario_id != usuario.id):
        raise NoEncontrado("venta no encontrada")
    return venta


def _es_ref_mp_duplicada(exc: IntegrityError) -> bool:
    """True si el IntegrityError es el unique de pago_venta.ref_mp (D10)."""
    return "ref_mp" in str(exc.orig)


def _es_check_de_stock(exc: IntegrityError) -> bool:
    """True si es un CHECK de stock no negativo (segunda defensa, D6.6)."""
    mensaje = str(exc.orig)
    return "no_negativo" in mensaje


def confirmar_venta(
    db: Session, venta_id: str, data: ConfirmarVentaRequest, usuario: Usuario
) -> Venta:
    """Confirma un borrador en UNA transaccion atomica (D6, RN-VT-01/02/04).

    1) carga + valida pagos (sin escribir); 2) compare-and-set borrador ->
    confirmada con rowcount (barrera contra doble confirmacion, tambien en
    SQLite); 3) lockea los productos ordenados y calcula faltantes de TODAS
    las lineas; 4) aplicar_movimiento(-cantidad, "venta", ref_id=venta) por
    linea en orden de producto_id; 5) pagos + evento venta.confirmada;
    6) UN commit. Ante cualquier error rollback total (deshace tambien el
    CAS) y re-raise. Repetir la confirmacion es replay (D9): 200 sin
    efectos si los pagos coinciden, 409 si difieren o la venta esta anulada.
    """
    venta = _cargar_venta(db, venta_id, usuario)
    _validar_pagos(venta, data.pagos)
    venta_id = venta.id
    try:
        cas = db.execute(
            update(Venta)
            .where(Venta.id == venta_id, Venta.estado == "borrador")
            .values(
                estado="confirmada",
                confirmada_at=datetime.now(timezone.utc),
                confirmada_por_id=usuario.id,
            ),
            execution_options={"synchronize_session": False},
        )
        if cas.rowcount == 0:
            return _replay_confirmacion(db, venta, data)

        lineas = sorted(venta.lineas, key=lambda li: li.producto_id)
        productos = _bloquear_productos(db, [li.producto_id for li in lineas])
        faltantes = _faltantes(lineas, productos)
        if faltantes:
            raise StockInsuficiente(faltantes)

        for linea in lineas:
            aplicar_movimiento(
                db,
                linea.producto_id,
                -linea.cantidad,
                "venta",
                usuario,
                motivo=f"venta {venta_id}",
                ref_id=venta_id,
            )
        for pago in data.pagos:
            db.add(
                PagoVenta(
                    venta_id=venta_id,
                    metodo=pago.metodo,
                    monto=pago.monto,
                    ref_mp=pago.ref_mp,
                )
            )
        registrar_evento(db, "venta.confirmada", venta_id)
        db.commit()
    except StockNegativo:
        db.rollback()
        raise StockInsuficiente(_faltantes_actuales(db, venta_id)) from None
    except IntegrityError as exc:
        db.rollback()
        if _es_ref_mp_duplicada(exc):
            raise RefMpDuplicada("ref_mp ya registrado en otro pago") from None
        if _es_check_de_stock(exc):
            raise StockInsuficiente(_faltantes_actuales(db, venta_id)) from None
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(venta)
    return venta


def _faltantes_actuales(db: Session, venta_id: str) -> list[dict]:
    """Faltantes recalculados con el stock vigente (tras un rollback)."""
    venta = db.get(Venta, venta_id)
    if venta is None:
        return []
    productos = {
        p.id: p
        for p in db.query(Producto)
        .filter(Producto.id.in_([li.producto_id for li in venta.lineas]))
        .populate_existing()
        .all()
    }
    return _faltantes(sorted(venta.lineas, key=lambda li: li.producto_id), productos)


def _replay_confirmacion(
    db: Session, venta: Venta, data: ConfirmarVentaRequest
) -> Venta:
    """Rama rowcount == 0 del CAS: la venta ya no esta en borrador (D9).

    Relee el estado real (otra request pudo ganar la carrera). Confirmada con
    el mismo multiconjunto (metodo, monto, ref_mp) de pagos => replay: se
    devuelve la venta sin efectos; con pagos distintos o anulada =>
    EstadoInvalido (409). No escribe nada.
    """
    db.rollback()
    db.refresh(venta)
    if venta.estado == "confirmada":
        previos = _firma_pagos([(p.metodo, p.monto, p.ref_mp) for p in venta.pagos])
        pedidos = _firma_pagos([(p.metodo, p.monto, p.ref_mp) for p in data.pagos])
        if previos == pedidos:
            return venta
        raise EstadoInvalido("la venta ya fue confirmada con otros pagos")
    raise EstadoInvalido(f"la venta esta {venta.estado}, no en borrador")


def anular_venta(
    db: Session, venta_id: str, data: AnularVentaRequest, usuario: Usuario
) -> Venta:
    """Anula una venta confirmada en UNA transaccion atomica (RN-VT-03, D3/D13).

    Solo la duena (el router lo exige). CAS confirmada -> anulada con
    rowcount; lockea los productos ordenados y, por linea, aplica un
    movimiento tipo `venta` de cantidad POSITIVA con ref_id a la venta y un
    motivo que identifica la anulacion (los movimientos originales y los
    pagos no se tocan: sin devolucion de dinero); registra el evento
    venta.anulada y hace UN commit. Ante cualquier error rollback total y
    re-raise. Anular una anulada es replay (200, sin efectos y sin comparar
    motivo, D9); anular un borrador es EstadoInvalido (409). Los productos
    dados de baja no impiden anular.
    """
    venta = _cargar_venta(db, venta_id, usuario)
    venta_id = venta.id
    try:
        cas = db.execute(
            update(Venta)
            .where(Venta.id == venta_id, Venta.estado == "confirmada")
            .values(
                estado="anulada",
                anulada_at=datetime.now(timezone.utc),
                anulada_por_id=usuario.id,
                motivo_anulacion=data.motivo,
            ),
            execution_options={"synchronize_session": False},
        )
        if cas.rowcount == 0:
            return _replay_anulacion(db, venta)

        lineas = sorted(venta.lineas, key=lambda li: li.producto_id)
        _bloquear_productos(db, [li.producto_id for li in lineas])
        for linea in lineas:
            aplicar_movimiento(
                db,
                linea.producto_id,
                linea.cantidad,
                "venta",
                usuario,
                motivo=f"anulacion venta {venta_id}: {data.motivo}",
                ref_id=venta_id,
            )
        registrar_evento(db, "venta.anulada", venta_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(venta)
    return venta


def _replay_anulacion(db: Session, venta: Venta) -> Venta:
    """Rama rowcount == 0 del CAS de anular (D9): relee el estado real.

    Anulada => replay sin efectos; borrador => EstadoInvalido (409).
    """
    db.rollback()
    db.refresh(venta)
    if venta.estado == "anulada":
        return venta
    raise EstadoInvalido(f"la venta esta {venta.estado}, no confirmada")


def obtener_venta(db: Session, venta_id: str, usuario: Usuario) -> Venta:
    """Detalle de una venta visible para `usuario` o NoEncontrado (D12)."""
    return _cargar_venta(db, venta_id, usuario)


def _paginar(query, page: int, page_size: int) -> tuple[list[Venta], int]:
    """created_at desc, id: paginado offset-based; devuelve (items, total)."""
    total = query.count()
    items = (
        query.order_by(Venta.created_at.desc(), Venta.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def listar_ventas(
    db: Session, filtros: VentaFiltros, usuario: Usuario
) -> tuple[list[Venta], int]:
    """Listado paginado con propiedad (D12) y filtros (D15).

    Un mostrador ve siempre solo sus ventas (un usuario_id ajeno da lista
    vacia). Sin `estado` solo confirmada y anulada (los borradores son
    inertes). desde/hasta son aware y se llevan a UTC: intervalo
    [desde, hasta) sobre created_at, sin asumir zona en el servidor.
    """
    query = db.query(Venta)
    if not _es_duena(usuario):
        query = query.filter(Venta.usuario_id == usuario.id)
    if filtros.usuario_id is not None:
        query = query.filter(Venta.usuario_id == filtros.usuario_id)
    if filtros.cliente_id is not None:
        query = query.filter(Venta.cliente_id == filtros.cliente_id)
    if filtros.estado is not None:
        query = query.filter(Venta.estado == filtros.estado)
    else:
        query = query.filter(Venta.estado.in_(ESTADOS_LISTADO))
    if filtros.desde is not None:
        query = query.filter(Venta.created_at >= filtros.desde.astimezone(timezone.utc))
    if filtros.hasta is not None:
        query = query.filter(Venta.created_at < filtros.hasta.astimezone(timezone.utc))
    return _paginar(query, filtros.page, filtros.page_size)


def ventas_de_cliente(
    db: Session, cliente_id: str, usuario: Usuario, page: int, page_size: int
) -> tuple[list[Venta], int]:
    """Historial de un cliente: confirmadas y anuladas, nunca borradores.

    NoEncontrado si el cliente no existe; un cliente dado de baja conserva
    su historial (C-09 D9). La propiedad se aplica tambien aca (D12): un
    mostrador ve solo las ventas del cliente que el mismo registro.
    """
    if db.get(Cliente, cliente_id) is None:
        raise NoEncontrado("cliente no encontrado")
    query = db.query(Venta).filter(
        Venta.cliente_id == cliente_id, Venta.estado.in_(ESTADOS_LISTADO)
    )
    if not _es_duena(usuario):
        query = query.filter(Venta.usuario_id == usuario.id)
    return _paginar(query, page, page_size)
