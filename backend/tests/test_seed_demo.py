"""Seed demo (C-13 B1, task 1.4, RED-first).

Corre sobre SQLite en memoria. Las contraseñas de los tests son valores
`test-only-*` pasados como argumento: el script no contiene ninguna.
"""

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func

from app.core.config import get_settings
from app.models import (
    Cliente,
    Distribuidora,
    ListaPrecio,
    MovimientoStock,
    PagoVenta,
    PedidoCompra,
    Producto,
    Usuario,
    Venta,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_DIR / "scripts" / "seed_demo.py"

OWNER_PWD = "test-only-owner-pwd"
MOSTRADOR_PWD = "test-only-mostrador-pwd"
OWNER_EMAIL = "duena@petshop.local"
MOSTRADOR_EMAIL = "mostrador@petshop.local"


def _seed(factory, **kwargs):
    from scripts.seed_demo import run_seed_demo

    params = {
        "owner_password": OWNER_PWD,
        "mostrador_password": MOSTRADOR_PWD,
        "env": "dev",
    }
    params.update(kwargs)
    return run_seed_demo(session_factory=factory, **params)


def _contar(factory) -> dict[str, int]:
    with factory() as s:
        return {
            "usuarios": s.query(Usuario).count(),
            "productos": s.query(Producto).count(),
            "distribuidoras": s.query(Distribuidora).count(),
            "listas": s.query(ListaPrecio).count(),
            "clientes": s.query(Cliente).count(),
            "pedidos": s.query(PedidoCompra).count(),
            "ventas": s.query(Venta).count(),
            "pagos": s.query(PagoVenta).count(),
            "movimientos": s.query(MovimientoStock).count(),
        }


def test_aborta_con_env_prod_y_no_modifica_la_base(db_session_factory) -> None:
    with pytest.raises(SystemExit) as exc:
        _seed(db_session_factory, env="prod")

    assert "dev" in str(exc.value.code)
    assert all(v == 0 for v in _contar(db_session_factory).values())


def test_sin_passwords_falla_nombrando_las_variables(
    db_session_factory, monkeypatch
) -> None:
    monkeypatch.delenv("SEED_OWNER_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_MOSTRADOR_PASSWORD", raising=False)

    with pytest.raises(SystemExit) as exc:
        _seed(db_session_factory, owner_password=None, mostrador_password=None)

    mensaje = str(exc.value.code)
    assert "SEED_OWNER_PASSWORD" in mensaje
    assert "SEED_MOSTRADOR_PASSWORD" in mensaje
    assert all(v == 0 for v in _contar(db_session_factory).values())


def test_falta_solo_una_variable_nombra_solo_esa(
    db_session_factory, monkeypatch
) -> None:
    monkeypatch.delenv("SEED_MOSTRADOR_PASSWORD", raising=False)

    with pytest.raises(SystemExit) as exc:
        _seed(db_session_factory, mostrador_password=None)

    mensaje = str(exc.value.code)
    assert "SEED_MOSTRADOR_PASSWORD" in mensaje
    assert "SEED_OWNER_PASSWORD" not in mensaje
    assert _contar(db_session_factory)["usuarios"] == 0


def test_passwords_se_leen_de_variables_de_entorno(
    db_session_factory, monkeypatch
) -> None:
    monkeypatch.setenv("SEED_OWNER_PASSWORD", OWNER_PWD)
    monkeypatch.setenv("SEED_MOSTRADOR_PASSWORD", MOSTRADOR_PWD)

    _seed(db_session_factory, owner_password=None, mostrador_password=None)

    with db_session_factory() as s:
        roles = {u.email: u.rol for u in s.query(Usuario).all()}
    assert roles == {OWNER_EMAIL: "duena", MOSTRADOR_EMAIL: "mostrador"}


def test_crea_duena_y_mostrador_con_password_valido(db_session_factory) -> None:
    from app.core.security import verify_password

    _seed(db_session_factory)

    with db_session_factory() as s:
        duena = s.query(Usuario).filter_by(email=OWNER_EMAIL).one()
        mostrador = s.query(Usuario).filter_by(email=MOSTRADOR_EMAIL).one()
    assert duena.rol == "duena" and duena.activo
    assert mostrador.rol == "mostrador" and mostrador.activo
    assert verify_password(OWNER_PWD, duena.password_hash)
    assert verify_password(MOSTRADOR_PWD, mostrador.password_hash)


def test_catalogo_productos_distribuidoras_y_clientes(db_session_factory) -> None:
    _seed(db_session_factory)

    with db_session_factory() as s:
        productos = s.query(Producto).filter(Producto.activo.is_(True)).all()
        assert len(productos) >= 15
        assert len({p.categoria for p in productos}) >= 4
        assert all(p.costo > 0 and p.margen_pct > 0 for p in productos)
        assert {p.unidad for p in productos} <= {"unidad", "bolsa", "caja"}
        sin_stock = [p for p in productos if p.stock_actual == 0]
        bajo_minimo = [p for p in productos if p.stock_actual <= p.stock_minimo]
        assert len(sin_stock) >= 1
        assert len(bajo_minimo) >= 3
        assert any(p.stock_actual > p.stock_minimo for p in productos)

        assert s.query(Distribuidora).count() >= 3
        assert s.query(Cliente).count() >= 6


def test_listas_de_precios_se_superponen(db_session_factory) -> None:
    _seed(db_session_factory)

    with db_session_factory() as s:
        por_producto: dict[str, set[str]] = defaultdict(set)
        for lp in s.query(ListaPrecio).all():
            por_producto[lp.producto_id].add(lp.distribuidora_id)
    assert any(len(dists) >= 2 for dists in por_producto.values())


def test_pedido_recibido_y_pedido_pendiente(db_session_factory) -> None:
    _seed(db_session_factory)

    with db_session_factory() as s:
        estados = [p.estado for p in s.query(PedidoCompra).all()]
    assert "recibido" in estados
    assert "pendiente" in estados


def test_ventas_en_varios_dias_con_anulada_y_tres_medios(db_session_factory) -> None:
    _seed(db_session_factory)

    zona = ZoneInfo(get_settings().reportes_tz)
    hoy = datetime.now(timezone.utc).astimezone(zona).date()

    with db_session_factory() as s:
        confirmadas = s.query(Venta).filter(Venta.estado == "confirmada").all()
        anuladas = s.query(Venta).filter(Venta.estado == "anulada").all()
        dias = {
            v.confirmada_at.replace(tzinfo=timezone.utc).astimezone(zona).date()
            for v in confirmadas
        }
        metodos = {m for (m,) in s.query(PagoVenta.metodo).distinct()}
        vendedores = {v.usuario_id for v in confirmadas}
        pagos_por_venta = dict(
            s.query(PagoVenta.venta_id, func.sum(PagoVenta.monto)).group_by(
                PagoVenta.venta_id
            )
        )
        totales = {v.id: v.total for v in confirmadas}

    assert len(dias) >= 3
    assert hoy in dias
    assert len(anuladas) >= 1
    assert anuladas[0].motivo_anulacion
    assert {"efectivo", "transferencia", "tarjeta"} <= metodos
    assert len(vendedores) == 2
    for vid, total in totales.items():
        assert round(float(pagos_por_venta[vid]), 2) == round(float(total), 2)


def test_cada_producto_con_stock_tiene_movimientos_consistentes(
    db_session_factory,
) -> None:
    _seed(db_session_factory)

    with db_session_factory() as s:
        productos = s.query(Producto).all()
        for p in productos:
            movs = (
                s.query(MovimientoStock)
                .filter(MovimientoStock.producto_id == p.id)
                .order_by(MovimientoStock.created_at, MovimientoStock.id)
                .all()
            )
            if p.stock_actual > 0:
                assert movs, f"{p.sku} tiene stock sin movimientos"
            assert sum(m.cantidad for m in movs) == p.stock_actual, p.sku
            assert "apertura" in {m.tipo for m in movs} or p.stock_actual == 0


def test_segunda_ejecucion_no_duplica_nada(db_session_factory) -> None:
    _seed(db_session_factory)
    antes = _contar(db_session_factory)

    segunda = _seed(db_session_factory)

    assert _contar(db_session_factory) == antes
    assert segunda["datos_creados"] is False


def test_segunda_ejecucion_no_pisa_passwords(db_session_factory) -> None:
    _seed(db_session_factory)
    with db_session_factory() as s:
        hashes = {u.email: u.password_hash for u in s.query(Usuario).all()}

    _seed(db_session_factory, owner_password="otro", mostrador_password="otro2")

    with db_session_factory() as s:
        assert {u.email: u.password_hash for u in s.query(Usuario).all()} == hashes


def test_script_sin_passwords_literales() -> None:
    texto = SCRIPT.read_text(encoding="utf-8")

    assert "SEED_OWNER_PASSWORD" in texto
    assert "SEED_MOSTRADOR_PASSWORD" in texto
    assert (
        re.search(r"password\s*=\s*['\"][^'\"]+['\"]", texto, re.IGNORECASE) is None
    )
    assert "demo-duena" not in texto and "demo-mostrador" not in texto


async def test_los_cuatro_reportes_devuelven_datos(
    client, db_session_factory
) -> None:
    _seed(db_session_factory)
    login = await client.post(
        "/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PWD}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    ventas_dia = (await client.get("/api/reportes/ventas-dia", headers=headers)).json()
    assert ventas_dia["cantidad_ventas"] >= 1
    assert float(ventas_dia["total_vendido"]) > 0

    mas_vendidos = (
        await client.get("/api/reportes/mas-vendidos", headers=headers)
    ).json()
    assert len(mas_vendidos["items"]) >= 3

    reposicion = (await client.get("/api/reportes/reposicion", headers=headers)).json()
    assert len(reposicion["items"]) >= 1

    margenes = (await client.get("/api/reportes/margenes", headers=headers)).json()
    assert len(margenes["items"]) >= 3
    assert float(margenes["totales"]["ingresos"]) > 0
