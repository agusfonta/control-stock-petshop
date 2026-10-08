"""Concurrencia real de ventas contra Postgres (C-10 task 7.3, pg_only).

SQLite no tiene FOR UPDATE ni escritores concurrentes, asi que aca se
ejercita el servicio con sesiones independientes en hilos (barrera para
largar juntos) contra Postgres: dos ventas por la ultima unidad, la misma
venta confirmada o anulada dos veces a la vez. Skip sin Postgres alcanzable
(mismo mecanismo que test_migration_pg.py: TEST_PG_URL). Los equivalentes
secuenciales corren siempre en test_ventas_confirmar/transiciones/anular.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.test_migration_pg import migrated_db, needs_pg  # noqa: F401


@pytest.fixture()
def pg_sessions(migrated_db):  # noqa: F811
    """sessionmaker contra la base migrada (pool > 1 para conexiones paralelas)."""
    engine = create_engine(migrated_db, pool_size=5, max_overflow=5)
    try:
        yield sessionmaker(bind=engine, autoflush=False, future=True)
    finally:
        engine.dispose()


def _sembrar(sessions, stock: int):
    """Usuario duena + producto (precio 1500) con `stock`; devuelve (uid, pid)."""
    from app.models import Producto, Usuario

    with sessions() as session:
        usuario = Usuario(
            email=f"{uuid.uuid4()}@test.only", password_hash="x", rol="duena"
        )
        producto = Producto(
            sku=f"CONC-{uuid.uuid4().hex[:8]}",
            nombre="Alimento",
            costo=1000,
            margen_pct=0.5,
            stock_actual=stock,
        )
        session.add_all([usuario, producto])
        session.commit()
        return usuario.id, producto.id


def _borrador(sessions, uid: str, pid: str, cantidad: int = 1) -> str:
    from app.models import Usuario
    from app.schemas import VentaCreate
    from app.services import ventas as svc

    with sessions() as session:
        usuario = session.get(Usuario, uid)
        data = VentaCreate.model_validate(
            {
                "idempotency_key": str(uuid.uuid4()),
                "lineas": [{"producto_id": pid, "cantidad": cantidad}],
            }
        )
        venta, creada = svc.crear_venta(session, data, usuario)
        assert creada
        return venta.id


def _en_paralelo(sessions, uid: str, tareas):
    """Corre cada tarea (fn(session, usuario)) en su hilo, largando juntas.

    Devuelve, por tarea, ('ok', resultado) o ('error', excepcion).
    """
    from app.models import Usuario

    barrera = threading.Barrier(len(tareas))

    def _correr(tarea):
        with sessions() as session:
            usuario = session.get(Usuario, uid)
            barrera.wait(timeout=30)
            try:
                return ("ok", tarea(session, usuario))
            except Exception as exc:  # noqa: BLE001 - se inspecciona en el test
                return ("error", exc)

    with ThreadPoolExecutor(max_workers=len(tareas)) as pool:
        futuros = [pool.submit(_correr, t) for t in tareas]
        return [f.result(timeout=60) for f in futuros]


def _confirmar(venta_id: str, pagos: list[dict]):
    from app.schemas import ConfirmarVentaRequest
    from app.services import ventas as svc

    data = ConfirmarVentaRequest.model_validate({"pagos": pagos})
    return lambda session, usuario: svc.confirmar_venta(session, venta_id, data, usuario)


def _estado(sessions, pid: str, venta_ids: list[str]):
    from app.models import MovimientoStock, PagoVenta, Producto, Venta

    with sessions() as session:
        return {
            "stock": session.get(Producto, pid).stock_actual,
            "movimientos": session.query(MovimientoStock)
            .filter_by(producto_id=pid)
            .count(),
            "pagos": session.query(PagoVenta)
            .filter(PagoVenta.venta_id.in_(venta_ids))
            .count(),
            "estados": sorted(
                str(v.estado)
                for v in session.query(Venta).filter(Venta.id.in_(venta_ids))
            ),
        }


@needs_pg
def test_dos_confirmaciones_por_la_ultima_unidad_una_gana_y_la_otra_409(
    pg_sessions,
) -> None:
    from app.services import ventas as svc

    uid, pid = _sembrar(pg_sessions, stock=1)
    v1 = _borrador(pg_sessions, uid, pid)
    v2 = _borrador(pg_sessions, uid, pid)
    resultados = _en_paralelo(
        pg_sessions,
        uid,
        [
            _confirmar(v1, [{"metodo": "efectivo", "monto": 1500}]),
            _confirmar(v2, [{"metodo": "efectivo", "monto": 1500}]),
        ],
    )
    oks = [r for r in resultados if r[0] == "ok"]
    errores = [r[1] for r in resultados if r[0] == "error"]
    assert len(oks) == 1
    assert len(errores) == 1 and isinstance(errores[0], svc.StockInsuficiente)
    estado = _estado(pg_sessions, pid, [v1, v2])
    assert estado["stock"] == 0
    assert estado["movimientos"] == 1
    assert estado["pagos"] == 1
    assert estado["estados"] == ["borrador", "confirmada"]


@needs_pg
def test_muchas_confirmaciones_concurrentes_nunca_dejan_stock_negativo(
    pg_sessions,
) -> None:
    uid, pid = _sembrar(pg_sessions, stock=3)
    ventas = [_borrador(pg_sessions, uid, pid) for _ in range(6)]
    resultados = _en_paralelo(
        pg_sessions,
        uid,
        [_confirmar(v, [{"metodo": "efectivo", "monto": 1500}]) for v in ventas],
    )
    assert sum(1 for r in resultados if r[0] == "ok") == 3
    estado = _estado(pg_sessions, pid, ventas)
    assert estado["stock"] == 0
    assert estado["movimientos"] == 3
    assert estado["estados"].count("confirmada") == 3


@needs_pg
def test_dos_confirmaciones_concurrentes_de_la_misma_venta_descuentan_una_vez(
    pg_sessions,
) -> None:
    uid, pid = _sembrar(pg_sessions, stock=5)
    venta = _borrador(pg_sessions, uid, pid, cantidad=2)
    pagos = [{"metodo": "efectivo", "monto": 3000}]
    resultados = _en_paralelo(
        pg_sessions, uid, [_confirmar(venta, pagos), _confirmar(venta, pagos)]
    )
    # Una confirma y la otra es replay (D9): las dos responden bien.
    assert [r[0] for r in resultados] == ["ok", "ok"]
    estado = _estado(pg_sessions, pid, [venta])
    assert estado["stock"] == 3
    assert estado["movimientos"] == 1
    assert estado["pagos"] == 1
    assert estado["estados"] == ["confirmada"]


@needs_pg
def test_dos_anulaciones_concurrentes_de_la_misma_venta_devuelven_stock_una_vez(
    pg_sessions,
) -> None:
    from app.schemas import AnularVentaRequest
    from app.services import ventas as svc

    uid, pid = _sembrar(pg_sessions, stock=5)
    venta = _borrador(pg_sessions, uid, pid, cantidad=2)
    resultados = _en_paralelo(
        pg_sessions, uid, [_confirmar(venta, [{"metodo": "efectivo", "monto": 3000}])]
    )
    assert resultados[0][0] == "ok"

    anular = AnularVentaRequest.model_validate({"motivo": "carrera de anulacion"})
    resultados = _en_paralelo(
        pg_sessions,
        uid,
        [
            lambda session, usuario: svc.anular_venta(session, venta, anular, usuario),
            lambda session, usuario: svc.anular_venta(session, venta, anular, usuario),
        ],
    )
    # Una anula y la otra es replay (D9): las dos responden bien.
    assert [r[0] for r in resultados] == ["ok", "ok"]
    estado = _estado(pg_sessions, pid, [venta])
    assert estado["stock"] == 5  # 5 - 2 (venta) + 2 (anulacion), una sola vez
    assert estado["movimientos"] == 2
    assert estado["estados"] == ["anulada"]


@needs_pg
def test_confirmar_y_anular_concurrentes_de_ventas_distintas_no_se_bloquean(
    pg_sessions,
) -> None:
    """Orden global de locks (cabecera, productos por id): sin deadlock."""
    from app.schemas import AnularVentaRequest
    from app.services import ventas as svc

    uid, pid = _sembrar(pg_sessions, stock=5)
    a_anular = _borrador(pg_sessions, uid, pid, cantidad=2)
    _en_paralelo(
        pg_sessions, uid, [_confirmar(a_anular, [{"metodo": "efectivo", "monto": 3000}])]
    )
    a_confirmar = _borrador(pg_sessions, uid, pid, cantidad=1)
    anular = AnularVentaRequest.model_validate({"motivo": "cruce"})
    resultados = _en_paralelo(
        pg_sessions,
        uid,
        [
            _confirmar(a_confirmar, [{"metodo": "efectivo", "monto": 1500}]),
            lambda session, usuario: svc.anular_venta(session, a_anular, anular, usuario),
        ],
    )
    assert [r[0] for r in resultados] == ["ok", "ok"]
    estado = _estado(pg_sessions, pid, [a_anular, a_confirmar])
    assert estado["stock"] == 4  # 5 - 2 + 2 - 1
    assert estado["estados"] == ["anulada", "confirmada"]
