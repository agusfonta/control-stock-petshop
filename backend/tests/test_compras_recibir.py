"""Recibir pedido: entradas de stock en una transaccion (C-07 task 5.1, RED-first).

POST /api/compras/pedidos/{id}/recibir suma stock de TODAS las lineas,
crea una entrada + un movimiento tipo entrada por linea (ref_id a la
entrada), actualiza el costo del producto (precio_venta se recalcula,
RN-PR-01) y marca el pedido recibido (RN-CP-01/02). En RED fallan: el
endpoint recibir no existe (404/405).
"""

import pytest

from tests.compras_helpers import (
    PEDIDOS_URL,
    agregar_a_lista,
    contar,
    crear_distribuidora,
    crear_pedido,
    crear_producto,
    get_producto,
    login_duena,
    login_mostrador,
    movimientos_de,
)


def _recibir_url(pedido_id: str) -> str:
    return f"{PEDIDOS_URL}/{pedido_id}/recibir"


async def _pedido_dos_lineas(client, headers):
    """A (stock 3, pide 10 a costo 800 de lista) y B (stock 0, pide 4 a 250)."""
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="REC-A", costo=1000, stock_actual=3)
    b = await crear_producto(client, headers, sku="REC-B", costo=250, stock_actual=0)
    await agregar_a_lista(client, headers, did, a, 800)
    pedido = await crear_pedido(client, headers, did, [(a, 10), (b, 4)])
    return did, a, b, pedido


async def test_recibir_suma_stock_de_todas_las_lineas(client) -> None:
    headers = await login_duena(client)
    _, a, b, pedido = await _pedido_dos_lineas(client, headers)
    response = await client.post(_recibir_url(pedido["id"]), headers=headers)
    assert response.status_code == 200
    assert (await get_producto(client, headers, a))["stock_actual"] == 13
    assert (await get_producto(client, headers, b))["stock_actual"] == 4


async def test_recibir_crea_un_movimiento_entrada_por_linea_con_ref_a_su_entrada(
    client, db_session_factory
) -> None:
    headers = await login_duena(client)
    _, a, b, pedido = await _pedido_dos_lineas(client, headers)
    body = (await client.post(_recibir_url(pedido["id"]), headers=headers)).json()
    entradas = {e["producto_id"]: e["id"] for e in body["entradas"]}
    assert set(entradas) == {a, b}

    (mov_a,) = movimientos_de(db_session_factory, a)
    assert (mov_a.tipo, mov_a.cantidad) == ("entrada", 10)
    assert (mov_a.stock_previo, mov_a.stock_nuevo) == (3, 13)
    assert mov_a.ref_id == entradas[a]

    (mov_b,) = movimientos_de(db_session_factory, b)
    assert (mov_b.tipo, mov_b.cantidad) == ("entrada", 4)
    assert (mov_b.stock_previo, mov_b.stock_nuevo) == (0, 4)
    assert mov_b.ref_id == entradas[b]


async def test_entrada_registra_cantidad_costo_y_usuario(client) -> None:
    headers = await login_duena(client)
    _, a, b, pedido = await _pedido_dos_lineas(client, headers)
    duena_id = (await client.get("/api/auth/me", headers=headers)).json()["id"]
    body = (await client.post(_recibir_url(pedido["id"]), headers=headers)).json()
    por_producto = {e["producto_id"]: e for e in body["entradas"]}
    assert (por_producto[a]["cantidad"], por_producto[a]["costo_unitario"]) == (10, 800)
    assert (por_producto[b]["cantidad"], por_producto[b]["costo_unitario"]) == (4, 250)
    assert {e["usuario_id"] for e in body["entradas"]} == {duena_id}


async def test_pedido_queda_recibido_con_fecha_y_usuario(client) -> None:
    headers = await login_duena(client)
    _, _, _, pedido = await _pedido_dos_lineas(client, headers)
    duena_id = (await client.get("/api/auth/me", headers=headers)).json()["id"]
    body = (await client.post(_recibir_url(pedido["id"]), headers=headers)).json()
    assert body["estado"] == "recibido"
    assert body["recibido_at"] is not None
    assert body["recibido_por_id"] == duena_id
    detalle = (await client.get(f"{PEDIDOS_URL}/{pedido['id']}", headers=headers)).json()
    assert detalle["estado"] == "recibido"
    assert len(detalle["entradas"]) == 2


async def test_recibir_actualiza_costo_y_precio_sugerido(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, costo=1000, margen_pct=0.5)
    await agregar_a_lista(client, headers, did, pid, 1200)
    pedido = await crear_pedido(client, headers, did, [(pid, 5)])
    assert (await client.post(_recibir_url(pedido["id"]), headers=headers)).status_code == 200
    producto = await get_producto(client, headers, pid)
    assert producto["costo"] == 1200
    assert producto["precio_venta"] == 1800


async def test_mostrador_puede_recibir_y_queda_registrado(
    client, db_session_factory
) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    _, a, _, pedido = await _pedido_dos_lineas(client, duena)
    mostrador_id = (await client.get("/api/auth/me", headers=mostrador)).json()["id"]
    response = await client.post(_recibir_url(pedido["id"]), headers=mostrador)
    assert response.status_code == 200
    body = response.json()
    assert body["recibido_por_id"] == mostrador_id
    assert {e["usuario_id"] for e in body["entradas"]} == {mostrador_id}
    assert {m.usuario_id for m in movimientos_de(db_session_factory, a)} == {mostrador_id}


async def test_recibir_anonimo_401_sin_cambios(client) -> None:
    duena = await login_duena(client)
    _, a, _, pedido = await _pedido_dos_lineas(client, duena)
    response = await client.post(_recibir_url(pedido["id"]))
    assert response.status_code == 401
    assert (await get_producto(client, duena, a))["stock_actual"] == 3


async def test_recibir_inexistente_404_sin_cambios(client, db_session_factory) -> None:
    from app.models import EntradaStock, MovimientoStock

    headers = await login_duena(client)
    _, a, _, _ = await _pedido_dos_lineas(client, headers)
    response = await client.post(_recibir_url("no-existe"), headers=headers)
    assert response.status_code == 404
    assert "pedido" in response.json()["detail"]
    assert (await get_producto(client, headers, a))["stock_actual"] == 3
    assert contar(db_session_factory, EntradaStock) == 0
    assert contar(db_session_factory, MovimientoStock) == 0


# --- Triangulacion (5.3) ---


async def test_fallo_en_segunda_linea_revierte_todo(
    client, db_session_factory, monkeypatch
) -> None:
    from app.models import EntradaStock, MovimientoStock, PedidoCompra
    from app.services import compras as svc_compras

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="ATO-A", costo=1000, stock_actual=3)
    b = await crear_producto(client, headers, sku="ATO-B", costo=250, stock_actual=1)
    await agregar_a_lista(client, headers, did, a, 800)
    await agregar_a_lista(client, headers, did, b, 300)
    pedido = await crear_pedido(client, headers, did, [(a, 10), (b, 4)])

    original = svc_compras.aplicar_movimiento
    llamadas = []

    def _falla_en_la_segunda(*args, **kwargs):
        llamadas.append(args[2])
        if len(llamadas) == 2:
            raise RuntimeError("falla simulada en la segunda linea")
        return original(*args, **kwargs)

    monkeypatch.setattr(svc_compras, "aplicar_movimiento", _falla_en_la_segunda)
    # El error no es de dominio: sube como 500 (el cliente de test lo re-lanza).
    with pytest.raises(RuntimeError, match="segunda linea"):
        await client.post(_recibir_url(pedido["id"]), headers=headers)
    # La primera linea SI llego a aplicarse dentro de la transaccion...
    assert len(llamadas) == 2
    monkeypatch.undo()

    # ...pero nada persiste: stock, costo, entradas, movimientos y estado.
    producto_a = await get_producto(client, headers, a)
    producto_b = await get_producto(client, headers, b)
    assert (producto_a["stock_actual"], producto_a["costo"]) == (3, 1000)
    assert (producto_b["stock_actual"], producto_b["costo"]) == (1, 250)
    assert contar(db_session_factory, EntradaStock) == 0
    assert contar(db_session_factory, MovimientoStock) == 0
    with db_session_factory() as session:
        assert session.get(PedidoCompra, pedido["id"]).estado == "pendiente"
        assert session.get(PedidoCompra, pedido["id"]).recibido_at is None
    # El pedido sigue siendo recibible despues del fallo.
    assert (await client.post(_recibir_url(pedido["id"]), headers=headers)).status_code == 200


def _capturar_updates_de_productos(db_session_factory):
    """Registra los UPDATE a productos para ver que columnas se escriben."""
    from sqlalchemy import event

    engine = db_session_factory.kw["bind"]
    sentencias: list[str] = []

    def _spy(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE PRODUCTOS"):
            sentencias.append(statement)

    event.listen(engine, "before_cursor_execute", _spy)
    return engine, _spy, sentencias


async def test_costo_igual_no_se_escribe_en_el_producto(
    client, db_session_factory
) -> None:
    from sqlalchemy import event

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, costo=1000, stock_actual=0)
    pedido = await crear_pedido(client, headers, did, [(pid, 5)])  # sin lista: 1000
    engine, spy, sentencias = _capturar_updates_de_productos(db_session_factory)
    try:
        assert (await client.post(_recibir_url(pedido["id"]), headers=headers)).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", spy)
    assert sentencias, "el stock del producto si se actualiza"
    assert not any("costo" in s for s in sentencias)
    producto = await get_producto(client, headers, pid)
    assert (producto["stock_actual"], producto["costo"], producto["precio_venta"]) == (
        5,
        1000,
        1500,
    )


async def test_costo_distinto_si_se_escribe_en_el_producto(
    client, db_session_factory
) -> None:
    from sqlalchemy import event

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, costo=1000)
    await agregar_a_lista(client, headers, did, pid, 900)
    pedido = await crear_pedido(client, headers, did, [(pid, 1)])
    engine, spy, sentencias = _capturar_updates_de_productos(db_session_factory)
    try:
        assert (await client.post(_recibir_url(pedido["id"]), headers=headers)).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", spy)
    assert any("costo" in s for s in sentencias)
    assert (await get_producto(client, headers, pid))["costo"] == 900


async def test_producto_y_distribuidora_dados_de_baja_igual_se_reciben(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, stock_actual=2)
    pedido = await crear_pedido(client, headers, did, [(pid, 6)])
    assert (await client.delete(f"/api/productos/{pid}", headers=headers)).status_code == 204
    assert (
        await client.delete(f"/api/distribuidoras/{did}", headers=headers)
    ).status_code == 204
    response = await client.post(_recibir_url(pedido["id"]), headers=headers)
    assert response.status_code == 200
    assert response.json()["estado"] == "recibido"
    assert (await get_producto(client, headers, pid))["stock_actual"] == 8


async def test_comparar_de_c06_sigue_devolviendo_el_sugerido_por_lista(client) -> None:
    headers = await login_duena(client)
    d1 = await crear_distribuidora(client, headers, nombre="Uno")
    d2 = await crear_distribuidora(client, headers, nombre="Dos")
    pid = await crear_producto(client, headers, costo=1000, margen_pct=0.5)
    await agregar_a_lista(client, headers, d1, pid, 1200)
    await agregar_a_lista(client, headers, d2, pid, 900)
    antes = (
        await client.get(
            "/api/distribuidoras/comparar", params={"producto_id": pid}, headers=headers
        )
    ).json()
    pedido = await crear_pedido(client, headers, d1, [(pid, 3)])
    assert (await client.post(_recibir_url(pedido["id"]), headers=headers)).status_code == 200
    despues = (
        await client.get(
            "/api/distribuidoras/comparar", params={"producto_id": pid}, headers=headers
        )
    ).json()
    assert despues == antes
    sugeridos = {f["distribuidora_id"]: f["precio_sugerido"] for f in despues["filas"]}
    assert sugeridos == {d1: 1800, d2: 1350}
    # El costo del producto SI cambio (ultimo costo recibido de d1).
    assert (await get_producto(client, headers, pid))["costo"] == 1200
