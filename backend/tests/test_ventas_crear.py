"""Crear venta en borrador e idempotencia del alta (C-10 task 5.1, RED-first).

POST /api/ventas crea el borrador con precio y total calculados por el
servidor (D5), sin tocar stock; chequea stock temprano con 409 y faltantes
(RN-VT-01 temprano, D7) y es idempotente por (usuario, idempotency_key)
(D8). En RED fallan: el router de ventas no existe (404/405).
"""

import pytest

from tests.ventas_helpers import (
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
    post_venta,
    usuario_id,
)


def _por_producto(venta: dict) -> dict:
    return {linea["producto_id"]: linea for linea in venta["lineas"]}


async def _a_y_b(client, duena):
    """A (precio 1500, stock 5) y B (precio 800, stock 1)."""
    a = await crear_producto(client, duena, sku="VC-A", costo=1000, margen_pct=0.5, stock_actual=5)
    b = await crear_producto(client, duena, sku="VC-B", costo=800, margen_pct=0, stock_actual=1)
    return a, b


# --- Borrador con precios del servidor ---


async def test_mostrador_crea_borrador_con_precio_y_total_del_servidor(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, b = await _a_y_b(client, duena)
    response = await post_venta(client, mostrador, [(a, 2), (b, 1)])
    assert response.status_code == 201
    venta = response.json()
    assert venta["estado"] == "borrador"
    assert venta["total"] == 3800
    lineas = _por_producto(venta)
    assert (lineas[a]["precio_unit"], lineas[a]["subtotal"], lineas[a]["cantidad"]) == (
        1500,
        3000,
        2,
    )
    assert (lineas[b]["precio_unit"], lineas[b]["subtotal"], lineas[b]["cantidad"]) == (
        800,
        800,
        1,
    )
    assert venta["usuario_id"] == await usuario_id(client, mostrador)
    assert venta["cliente_id"] is None
    assert venta["pagos"] == []
    assert venta["confirmada_at"] is None


async def test_crear_borrador_no_toca_stock_movimientos_ni_pagos(
    client, db_session_factory
) -> None:
    from app.models import MovimientoStock, PagoVenta

    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    await crear_venta(client, duena, [(a, 2), (b, 1)])
    assert (await get_producto(client, duena, a))["stock_actual"] == 5
    assert (await get_producto(client, duena, b))["stock_actual"] == 1
    assert movimientos_de(db_session_factory, a) == []
    assert contar(db_session_factory, MovimientoStock) == 0
    assert contar(db_session_factory, PagoVenta) == 0


async def test_duena_tambien_crea_borrador(client) -> None:
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    venta = await crear_venta(client, duena, [(a, 1)])
    assert venta["usuario_id"] == await usuario_id(client, duena)


async def test_venta_sin_cliente_201(client) -> None:
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    response = await post_venta(client, duena, [(a, 1)])
    assert response.status_code == 201
    assert response.json()["cliente_id"] is None


async def test_venta_con_cliente_activo_201(client) -> None:
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    cliente_id = await crear_cliente(client, duena)
    venta = await crear_venta(client, duena, [(a, 1)], cliente_id=cliente_id)
    assert venta["cliente_id"] == cliente_id


async def test_precio_con_mas_de_dos_decimales_se_redondea_mitad_hacia_arriba(
    client,
) -> None:
    duena = await login_duena(client)
    p = await crear_producto(client, duena, sku="VC-RD", costo=10.03, margen_pct=0.5, stock_actual=5)
    venta = await crear_venta(client, duena, [(p, 2)])
    (linea,) = venta["lineas"]
    assert linea["precio_unit"] == 15.05
    assert linea["subtotal"] == 30.1
    assert venta["total"] == 30.1


async def test_redondeo_parte_del_valor_exacto_sin_doble_redondeo(client) -> None:
    """costo 1.01 x (1 + 0.5396) = 1.554996: se redondea UNA vez => 1.55.

    Redondear antes a 4 decimales (1.5550) y luego a centavos daria 1.56.
    """
    duena = await login_duena(client)
    p = await crear_producto(client, duena, sku="VC-DR", costo=1.01, margen_pct=0.5396, stock_actual=5)
    venta = await crear_venta(client, duena, [(p, 1)])
    assert venta["lineas"][0]["precio_unit"] == 1.55
    assert venta["total"] == 1.55


async def test_total_es_la_suma_de_subtotales_redondeados_por_linea(client) -> None:
    duena = await login_duena(client)
    p1 = await crear_producto(client, duena, sku="VC-T1", costo=10.03, margen_pct=0.5, stock_actual=9)
    p2 = await crear_producto(client, duena, sku="VC-T2", costo=3.33, margen_pct=0, stock_actual=9)
    venta = await crear_venta(client, duena, [(p1, 3), (p2, 3)])
    lineas = _por_producto(venta)
    assert lineas[p1]["subtotal"] == 45.15  # 3 x 15.05
    assert lineas[p2]["subtotal"] == 9.99  # 3 x 3.33
    assert venta["total"] == 55.14


# --- Validaciones del body ---


@pytest.mark.parametrize(
    "extra",
    [{"total": 100}, {"estado": "confirmada"}, {"usuario_id": "otro"}],
)
async def test_campo_del_servidor_en_la_venta_rechazado_422(
    client, db_session_factory, extra
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    response = await post_venta(client, duena, [(a, 1)], **extra)
    assert response.status_code == 422
    assert contar(db_session_factory, Venta) == 0


async def test_precio_unit_en_la_linea_rechazado_422(client, db_session_factory) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    response = await client.post(
        VENTAS_URL,
        json={
            "idempotency_key": clave_nueva(),
            "lineas": [{"producto_id": a, "cantidad": 1, "precio_unit": 1}],
        },
        headers=duena,
    )
    assert response.status_code == 422
    assert contar(db_session_factory, Venta) == 0


@pytest.mark.parametrize("cantidad", [0, -1, 1.5])
async def test_cantidad_invalida_422(client, db_session_factory, cantidad) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    response = await post_venta(client, duena, [(a, cantidad)])
    assert response.status_code == 422
    assert contar(db_session_factory, Venta) == 0


async def test_lineas_vacias_y_producto_repetido_422(client, db_session_factory) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    assert (await post_venta(client, duena, [])).status_code == 422
    assert (await post_venta(client, duena, [(a, 1), (a, 2)])).status_code == 422
    assert contar(db_session_factory, Venta) == 0


async def test_producto_inexistente_404_y_dado_de_baja_422(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    inexistente = await post_venta(client, duena, [(a, 1), ("no-existe", 1)])
    assert inexistente.status_code == 404
    baja = await client.delete(f"/api/productos/{b}", headers=duena)
    assert baja.status_code == 204
    inactivo = await post_venta(client, duena, [(a, 1), (b, 1)])
    assert inactivo.status_code == 422
    assert contar(db_session_factory, Venta) == 0


async def test_cliente_inexistente_404_y_dado_de_baja_422(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    inexistente = await post_venta(client, duena, [(a, 1)], cliente_id="no-existe")
    assert inexistente.status_code == 404
    cliente_id = await crear_cliente(client, duena)
    baja = await client.delete(f"/api/clientes/{cliente_id}", headers=duena)
    assert baja.status_code == 204
    inactivo = await post_venta(client, duena, [(a, 1)], cliente_id=cliente_id)
    assert inactivo.status_code == 422
    assert contar(db_session_factory, Venta) == 0


async def test_cambio_de_costo_posterior_no_altera_el_borrador(client) -> None:
    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    venta = await crear_venta(client, duena, [(a, 2)])
    assert venta["total"] == 3000
    subida = await client.put(f"/api/productos/{a}", json={"costo": 2000}, headers=duena)
    assert subida.status_code == 200
    assert (await get_producto(client, duena, a))["precio_venta"] == 3000
    releida = await get_venta(client, duena, venta["id"])
    assert releida["lineas"][0]["precio_unit"] == 1500
    assert releida["total"] == 3000


# --- Bloqueo duro por stock (RN-VT-01 temprano, D7) ---


async def test_cantidad_mayor_al_stock_409_con_faltantes_sin_crear_venta(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    p = await crear_producto(client, duena, sku="VC-S2", stock_actual=2)
    response = await post_venta(client, duena, [(p, 3)])
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "mensaje": "stock insuficiente",
        "faltantes": [{"producto_id": p, "solicitado": 3, "disponible": 2}],
    }
    assert contar(db_session_factory, Venta) == 0
    assert (await get_producto(client, duena, p))["stock_actual"] == 2


async def test_faltantes_lista_solo_las_lineas_sin_stock(client) -> None:
    duena = await login_duena(client)
    ok = await crear_producto(client, duena, sku="VC-OK", stock_actual=10)
    corto = await crear_producto(client, duena, sku="VC-CO", stock_actual=1)
    cero = await crear_producto(client, duena, sku="VC-ZE", stock_actual=0)
    response = await post_venta(client, duena, [(ok, 2), (corto, 4), (cero, 1)])
    assert response.status_code == 409
    assert response.json()["detail"]["faltantes"] == [
        {"producto_id": corto, "solicitado": 4, "disponible": 1},
        {"producto_id": cero, "solicitado": 1, "disponible": 0},
    ]


async def test_cantidad_igual_al_stock_se_acepta(client) -> None:
    duena = await login_duena(client)
    p = await crear_producto(client, duena, sku="VC-EQ", stock_actual=2)
    response = await post_venta(client, duena, [(p, 2)])
    assert response.status_code == 201


# --- Idempotencia del alta (D8) ---


async def test_misma_clave_mismo_contenido_devuelve_la_misma_venta(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    clave = clave_nueva()
    primera = await post_venta(client, duena, [(a, 2), (b, 1)], clave=clave)
    segunda = await post_venta(client, duena, [(b, 1), (a, 2)], clave=clave)
    assert primera.status_code == 201
    assert segunda.status_code == 200
    assert segunda.json()["id"] == primera.json()["id"]
    assert contar(db_session_factory, Venta) == 1


async def test_replay_no_revalida_stock_ni_recotiza(client) -> None:
    duena = await login_duena(client)
    p = await crear_producto(client, duena, sku="VC-RP", costo=1000, margen_pct=0.5, stock_actual=2)
    clave = clave_nueva()
    primera = await post_venta(client, duena, [(p, 2)], clave=clave)
    assert primera.status_code == 201
    consumo = await client.post(
        f"/api/productos/{p}/ajustar",
        json={"cantidad_delta": -2, "motivo": "rotura"},
        headers=duena,
    )
    assert consumo.status_code == 200
    await client.put(f"/api/productos/{p}", json={"costo": 5000}, headers=duena)
    segunda = await post_venta(client, duena, [(p, 2)], clave=clave)
    assert segunda.status_code == 200
    assert segunda.json()["id"] == primera.json()["id"]
    assert segunda.json()["total"] == 3000


async def test_misma_clave_otro_contenido_422_sin_cambios(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, b = await _a_y_b(client, duena)
    cliente_id = await crear_cliente(client, duena)
    clave = clave_nueva()
    original = await post_venta(client, duena, [(a, 2)], clave=clave)
    assert original.status_code == 201
    for lineas, cliente in [
        ([(a, 3)], None),  # otra cantidad
        ([(a, 2), (b, 1)], None),  # otra linea
        ([(b, 1)], None),  # otro producto
        ([(a, 2)], cliente_id),  # otro cliente
    ]:
        respuesta = await post_venta(client, duena, lineas, clave=clave, cliente_id=cliente)
        assert respuesta.status_code == 422
    assert contar(db_session_factory, Venta) == 1
    intacta = await get_venta(client, duena, original.json()["id"])
    assert intacta["total"] == 3000
    assert [(ln["producto_id"], ln["cantidad"]) for ln in intacta["lineas"]] == [(a, 2)]
    assert intacta["cliente_id"] is None


async def test_misma_clave_de_otro_usuario_crea_venta_nueva_sin_tocar_la_ajena(
    client, db_session_factory
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    a, b = await _a_y_b(client, duena)
    clave = clave_nueva()
    de_duena = await post_venta(client, duena, [(a, 2)], clave=clave)
    de_mostrador = await post_venta(client, mostrador, [(b, 1)], clave=clave)
    assert de_duena.status_code == 201
    assert de_mostrador.status_code == 201
    assert de_mostrador.json()["id"] != de_duena.json()["id"]
    assert de_mostrador.json()["usuario_id"] == await usuario_id(client, mostrador)
    assert contar(db_session_factory, Venta) == 2
    intacta = await get_venta(client, duena, de_duena.json()["id"])
    assert [(ln["producto_id"], ln["cantidad"]) for ln in intacta["lineas"]] == [(a, 2)]


@pytest.mark.parametrize("clave", [None, "no-es-uuid", "", 123])
async def test_idempotency_key_invalida_o_ausente_422(
    client, db_session_factory, clave
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    cuerpo = {"lineas": [{"producto_id": a, "cantidad": 1}]}
    if clave is not None:
        cuerpo["idempotency_key"] = clave
    response = await client.post(VENTAS_URL, json=cuerpo, headers=duena)
    assert response.status_code == 422
    assert contar(db_session_factory, Venta) == 0


async def test_alta_sin_autenticacion_401(client, db_session_factory) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    response = await client.post(
        VENTAS_URL,
        json={"idempotency_key": clave_nueva(), "lineas": [{"producto_id": a, "cantidad": 1}]},
    )
    assert response.status_code == 401
    assert contar(db_session_factory, Venta) == 0


# --- Carrera por la clave de idempotencia (task 5.3, D8) ---


def _insertar_rival(db_session_factory, usuario_id: str, clave: str, lineas, cliente_id=None):
    """Inserta a mano la venta que 'gano' la carrera por la misma clave."""
    from decimal import Decimal

    from app.models import LineaVenta, Venta

    with db_session_factory() as session:
        venta = Venta(
            usuario_id=usuario_id,
            idempotency_key=clave,
            cliente_id=cliente_id,
            total=Decimal(0),
        )
        total = Decimal(0)
        for producto_id, cantidad in lineas:
            subtotal = Decimal("1500") * cantidad
            total += subtotal
            venta.lineas.append(
                LineaVenta(
                    producto_id=producto_id,
                    cantidad=cantidad,
                    precio_unit=Decimal("1500"),
                    subtotal=subtotal,
                )
            )
        venta.total = total
        session.add(venta)
        session.commit()
        return venta.id


def _perder_la_carrera(monkeypatch, db_session_factory, lineas_rival):
    """La 1a busqueda por clave ve vacio y justo despues entra la venta rival."""
    from app.services import ventas as svc

    real = svc._buscar_por_clave
    estado = {"llamadas": 0, "rival_id": None}

    def _buscar(db, usuario_id, clave):
        estado["llamadas"] += 1
        if estado["llamadas"] == 1:
            assert real(db, usuario_id, clave) is None
            estado["rival_id"] = _insertar_rival(
                db_session_factory, usuario_id, clave, lineas_rival
            )
            return None
        return real(db, usuario_id, clave)

    monkeypatch.setattr(svc, "_buscar_por_clave", _buscar)
    return estado


async def test_carrera_de_clave_con_mismo_contenido_se_resuelve_como_replay_200(
    client, db_session_factory, monkeypatch
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    estado = _perder_la_carrera(monkeypatch, db_session_factory, [(a, 2)])
    response = await post_venta(client, duena, [(a, 2)])
    assert response.status_code == 200
    assert response.json()["id"] == estado["rival_id"]
    assert contar(db_session_factory, Venta) == 1


async def test_carrera_de_clave_con_otro_contenido_se_resuelve_como_422(
    client, db_session_factory, monkeypatch
) -> None:
    from app.models import Venta

    duena = await login_duena(client)
    a, _ = await _a_y_b(client, duena)
    _perder_la_carrera(monkeypatch, db_session_factory, [(a, 1)])
    response = await post_venta(client, duena, [(a, 2)])
    assert response.status_code == 422
    assert contar(db_session_factory, Venta) == 1
