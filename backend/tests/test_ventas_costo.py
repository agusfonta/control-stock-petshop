"""Costo congelado en la linea de venta (C-14 task 3.1, RED-first, D1).

`crear_venta` congela junto con `precio_unit` el `Producto.costo` vigente en
`linea_venta.costo_unit` (para el margen historico de C-14). El costo lo fija
el servidor, no cambia con el costo del producto y NUNCA sale por la API de
ventas (el mostrador no debe ver costos). En RED fallan por la columna
`costo_unit` inexistente en LineaVenta.
"""

from decimal import Decimal

import pytest

from tests.ventas_helpers import (
    CLIENTES_URL,
    VENTAS_URL,
    clave_nueva,
    crear_cliente,
    crear_producto,
    crear_venta,
    login_duena,
    login_mostrador,
    pago,
    post_anular,
    post_confirmar,
    post_venta,
    venta_confirmada,
)


def _costos_de(db_session_factory, venta_id: str) -> dict[str, Decimal]:
    """costo_unit por producto leido por una sesion de base, no por la API."""
    from app.models import LineaVenta

    with db_session_factory() as session:
        filas = session.query(LineaVenta).filter_by(venta_id=venta_id).all()
        return {
            linea.producto_id: (
                None if linea.costo_unit is None else Decimal(str(linea.costo_unit))
            )
            for linea in filas
        }


def _claves(valor) -> set[str]:
    """Todas las claves de un JSON anidado (dicts y listas)."""
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _claves(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _claves(v)}
    return set()


async def _producto(client, duena, sku="VCO-A", costo=1000, stock=10) -> str:
    return await crear_producto(
        client, duena, sku=sku, costo=costo, margen_pct=0.5, stock_actual=stock
    )


# --- Se congela al crear el borrador ---


async def test_borrador_congela_el_costo_vigente_del_producto(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, "VCO-A", costo=1000)
    b = await _producto(client, duena, "VCO-B", costo=800)
    venta = await crear_venta(client, duena, [(a, 2), (b, 1)])
    assert _costos_de(db_session_factory, venta["id"]) == {
        a: Decimal("1000"),
        b: Decimal("800"),
    }


async def test_costo_con_centavos_se_congela_exacto(client, db_session_factory) -> None:
    """100.01 pasa por Decimal(str(...)): sin ruido de float."""
    duena = await login_duena(client)
    a = await _producto(client, duena, "VCO-C", costo=100.01)
    venta = await crear_venta(client, duena, [(a, 1)])
    assert _costos_de(db_session_factory, venta["id"]) == {a: Decimal("100.01")}


async def test_cambio_de_costo_posterior_no_altera_el_costo_congelado(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, costo=1000)
    venta = await crear_venta(client, duena, [(a, 2)])
    subida = await client.put(f"/api/productos/{a}", json={"costo": 1200}, headers=duena)
    assert subida.status_code == 200
    assert _costos_de(db_session_factory, venta["id"]) == {a: Decimal("1000")}


async def test_el_costo_congelado_sobrevive_a_la_confirmacion(
    client, db_session_factory
) -> None:
    """Confirmar no re-cotiza: sigue el costo del borrador aunque el vigente cambie."""
    duena = await login_duena(client)
    a = await _producto(client, duena, costo=1000)
    borrador = await crear_venta(client, duena, [(a, 2)])
    await client.put(f"/api/productos/{a}", json={"costo": 1200}, headers=duena)
    confirmada = await post_confirmar(client, duena, borrador["id"], [pago(monto=3000)])
    assert confirmada.status_code == 200
    assert _costos_de(db_session_factory, borrador["id"]) == {a: Decimal("1000")}


async def test_replay_idempotente_no_recalcula_el_costo(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, costo=1000)
    clave = clave_nueva()
    primera = await post_venta(client, duena, [(a, 2)], clave=clave)
    assert primera.status_code == 201
    await client.put(f"/api/productos/{a}", json={"costo": 1200}, headers=duena)
    segunda = await post_venta(client, duena, [(a, 2)], clave=clave)
    assert segunda.status_code == 200
    assert _costos_de(db_session_factory, primera.json()["id"]) == {a: Decimal("1000")}


async def test_una_venta_posterior_toma_el_costo_nuevo(client, db_session_factory) -> None:
    duena = await login_duena(client)
    a = await _producto(client, duena, costo=1000)
    vieja = await crear_venta(client, duena, [(a, 1)])
    await client.put(f"/api/productos/{a}", json={"costo": 1200}, headers=duena)
    nueva = await crear_venta(client, duena, [(a, 1)])
    assert _costos_de(db_session_factory, vieja["id"]) == {a: Decimal("1000")}
    assert _costos_de(db_session_factory, nueva["id"]) == {a: Decimal("1200")}


# --- El cliente no lo envia ---


async def test_costo_unit_en_la_linea_rechazado_422_sin_crear_venta(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a = await _producto(client, duena)
    body = {
        "idempotency_key": clave_nueva(),
        "lineas": [{"producto_id": a, "cantidad": 1, "costo_unit": 1}],
    }
    response = await client.post(VENTAS_URL, json=body, headers=duena)
    assert response.status_code == 422
    with db_session_factory() as session:
        assert session.query(Venta).count() == 0


# --- Nunca se expone en la API de ventas ---


async def test_ninguna_respuesta_de_la_api_de_ventas_expone_costo_unit(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a = await _producto(client, duena, "VCO-X", costo=1000)
    b = await _producto(client, duena, "VCO-Y", costo=800)
    cliente_id = await crear_cliente(client, duena)

    borrador = await post_venta(client, mostrador, [(a, 1)])
    confirmada = await venta_confirmada(
        client, mostrador, [(b, 1)], [pago(monto=1200)], cliente_id=cliente_id
    )
    anulada = await post_anular(client, duena, confirmada["id"])
    detalle = await client.get(f"{VENTAS_URL}/{confirmada['id']}", headers=duena)
    listado = await client.get(VENTAS_URL, headers=duena)
    historial = await client.get(
        f"{CLIENTES_URL}/{cliente_id}/ventas", headers=duena
    )
    confirmar = await post_confirmar(
        client, mostrador, borrador.json()["id"], [pago(monto=1500)]
    )

    respuestas = {
        "crear": borrador,
        "confirmar": confirmar,
        "anular": anulada,
        "detalle": detalle,
        "listado": listado,
        "historial": historial,
    }
    for nombre, respuesta in respuestas.items():
        assert respuesta.status_code in (200, 201), (nombre, respuesta.text)
        assert "costo_unit" not in _claves(respuesta.json()), nombre
        assert "costo" not in _claves(respuesta.json()), nombre


# --- Modelo: restriccion de la columna ---


def _base(db_session_factory):
    from app.models import Producto, Usuario
    from tests.conftest import DUENA_EMAIL

    with db_session_factory() as session:
        duena = session.query(Usuario).filter_by(email=DUENA_EMAIL).one()
        producto = Producto(sku="VCO-M", nombre="Alimento", costo=1000)
        session.add(producto)
        session.commit()
        return duena.id, producto.id


@pytest.mark.parametrize("costo", [None, Decimal("0.01"), Decimal("1000")])
def test_base_acepta_costo_unit_nulo_o_positivo(
    db_session_factory, seed_users, costo
) -> None:
    from app.models import LineaVenta, Venta

    uid, pid = _base(db_session_factory)
    with db_session_factory() as session:
        venta = Venta(usuario_id=uid, total=3000, idempotency_key=clave_nueva())
        venta.lineas.append(
            LineaVenta(
                producto_id=pid,
                cantidad=2,
                precio_unit=1500,
                subtotal=3000,
                costo_unit=costo,
            )
        )
        session.add(venta)
        session.commit()
        guardado = session.query(LineaVenta).one().costo_unit
        assert (guardado is None) == (costo is None)
        if costo is not None:
            assert Decimal(str(guardado)) == costo
