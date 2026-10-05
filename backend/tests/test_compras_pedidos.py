"""Crear y consultar pedidos de compra (C-07 task 4.1, RED-first).

POST/GET /api/compras/pedidos y GET /api/compras/pedidos/{id}. Crear no
mueve stock (RN-CP-02); el costo de linea sale de la lista de la
distribuidora o del producto (RN-CP-01) y nunca del cliente (D6).
En RED fallan: el router /api/compras no existe (404).
"""

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
    post_pedido,
)


async def test_crear_pedido_201_sin_mover_stock_ni_movimientos(
    client, db_session_factory
) -> None:
    from app.models import MovimientoStock

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, stock_actual=3)
    response = await post_pedido(client, headers, did, [(pid, 10)], notas="urgente")
    assert response.status_code == 201
    body = response.json()
    assert body["estado"] == "pendiente"
    assert body["distribuidora_id"] == did
    assert body["notas"] == "urgente"
    assert body["recibido_at"] is None
    assert body["entradas"] == []
    assert len(body["lineas"]) == 1
    assert body["lineas"][0]["cantidad"] == 10
    assert (await get_producto(client, headers, pid))["stock_actual"] == 3
    assert movimientos_de(db_session_factory, pid) == []
    assert contar(db_session_factory, MovimientoStock) == 0


async def test_costo_de_linea_tomado_de_la_lista(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, costo=1000)
    await agregar_a_lista(client, headers, did, pid, 800)
    pedido = await crear_pedido(client, headers, did, [(pid, 2)])
    assert pedido["lineas"][0]["costo_unitario"] == 800


async def test_costo_de_linea_sin_lista_usa_costo_del_producto(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    otra = await crear_distribuidora(client, headers, nombre="Otra")
    pid = await crear_producto(client, headers, costo=1000)
    # La lista de OTRA distribuidora no aplica a este pedido.
    await agregar_a_lista(client, headers, otra, pid, 700)
    pedido = await crear_pedido(client, headers, did, [(pid, 2)])
    assert pedido["lineas"][0]["costo_unitario"] == 1000


async def test_mostrador_puede_crear_pedido_y_queda_como_creador(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    did = await crear_distribuidora(client, duena)
    pid = await crear_producto(client, duena)
    mostrador_id = (await client.get("/api/auth/me", headers=mostrador)).json()["id"]
    response = await post_pedido(client, mostrador, did, [(pid, 1)])
    assert response.status_code == 201
    assert response.json()["usuario_id"] == mostrador_id


async def test_crear_pedido_anonimo_401(client) -> None:
    response = await client.post(
        PEDIDOS_URL,
        json={"distribuidora_id": "d", "lineas": [{"producto_id": "p", "cantidad": 1}]},
    )
    assert response.status_code == 401


async def test_crear_pedido_distribuidora_inexistente_404(
    client, db_session_factory
) -> None:
    from app.models import PedidoCompra

    headers = await login_duena(client)
    pid = await crear_producto(client, headers)
    response = await post_pedido(client, headers, "no-existe", [(pid, 1)])
    assert response.status_code == 404
    assert "distribuidora" in response.json()["detail"]
    assert contar(db_session_factory, PedidoCompra) == 0


async def test_crear_pedido_producto_inexistente_404(
    client, db_session_factory
) -> None:
    from app.models import PedidoCompra

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers)
    response = await post_pedido(client, headers, did, [(pid, 1), ("no-existe", 1)])
    assert response.status_code == 404
    assert "producto" in response.json()["detail"]
    assert contar(db_session_factory, PedidoCompra) == 0


async def test_crear_pedido_distribuidora_inactiva_422(
    client, db_session_factory
) -> None:
    from app.models import PedidoCompra

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers)
    assert (
        await client.delete(f"/api/distribuidoras/{did}", headers=headers)
    ).status_code == 204
    response = await post_pedido(client, headers, did, [(pid, 1)])
    assert response.status_code == 422
    assert contar(db_session_factory, PedidoCompra) == 0


async def test_crear_pedido_producto_inactivo_422(client, db_session_factory) -> None:
    from app.models import PedidoCompra

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    activo = await crear_producto(client, headers, sku="CMP-A")
    inactivo = await crear_producto(client, headers, sku="CMP-B")
    assert (
        await client.delete(f"/api/productos/{inactivo}", headers=headers)
    ).status_code == 204
    response = await post_pedido(client, headers, did, [(activo, 1), (inactivo, 1)])
    assert response.status_code == 422
    assert contar(db_session_factory, PedidoCompra) == 0


async def test_crear_pedido_payload_invalido_422(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers)
    assert (await post_pedido(client, headers, did, [])).status_code == 422
    assert (await post_pedido(client, headers, did, [(pid, 0)])).status_code == 422
    assert (
        await post_pedido(client, headers, did, [(pid, 1), (pid, 2)])
    ).status_code == 422
    con_costo = await client.post(
        PEDIDOS_URL,
        json={
            "distribuidora_id": did,
            "lineas": [{"producto_id": pid, "cantidad": 1, "costo_unitario": 1}],
        },
        headers=headers,
    )
    assert con_costo.status_code == 422


async def _insertar_pedido_cancelado(db_session_factory, did: str) -> str:
    """Un pedido en estado cancelado, insertado directo (el endpoint llega en 6.2)."""
    from app.models import PedidoCompra, Usuario

    with db_session_factory() as session:
        uid = session.query(Usuario).first().id
        pedido = PedidoCompra(distribuidora_id=did, usuario_id=uid, estado="cancelado")
        session.add(pedido)
        session.commit()
        return pedido.id


async def test_listar_filtra_por_estado_pendiente(client, db_session_factory) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers)
    pendiente = await crear_pedido(client, headers, did, [(pid, 1)])
    cancelado_id = await _insertar_pedido_cancelado(db_session_factory, did)
    response = await client.get(
        PEDIDOS_URL, params={"estado": "pendiente"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert [p["id"] for p in body["items"]] == [pendiente["id"]]
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 1
    sin_filtro = (await client.get(PEDIDOS_URL, headers=headers)).json()
    assert {p["id"] for p in sin_filtro["items"]} == {pendiente["id"], cancelado_id}


async def test_listar_estado_invalido_422(client) -> None:
    headers = await login_duena(client)
    response = await client.get(
        PEDIDOS_URL, params={"estado": "enviado"}, headers=headers
    )
    assert response.status_code == 422


async def test_listar_anonimo_401(client) -> None:
    assert (await client.get(PEDIDOS_URL)).status_code == 401


async def test_mostrador_puede_listar_pedidos(client) -> None:
    mostrador = await login_mostrador(client)
    response = await client.get(PEDIDOS_URL, headers=mostrador)
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_detalle_con_subtotales_y_total_estimado(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="CMP-A", costo=1000)
    b = await crear_producto(client, headers, sku="CMP-B", costo=200)
    await agregar_a_lista(client, headers, did, a, 800)
    creado = await crear_pedido(client, headers, did, [(a, 10), (b, 5)])
    response = await client.get(f"{PEDIDOS_URL}/{creado['id']}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    subtotales = {linea["producto_id"]: linea["subtotal"] for linea in body["lineas"]}
    assert subtotales == {a: 8000, b: 1000}
    assert body["total_estimado"] == 9000
    assert body["entradas"] == []


async def test_detalle_inexistente_404(client) -> None:
    headers = await login_duena(client)
    response = await client.get(f"{PEDIDOS_URL}/no-existe", headers=headers)
    assert response.status_code == 404
    assert "pedido" in response.json()["detail"]


# --- Triangulacion (4.3) ---


async def test_listar_filtra_por_distribuidora_id(client) -> None:
    headers = await login_duena(client)
    d1 = await crear_distribuidora(client, headers, nombre="Uno")
    d2 = await crear_distribuidora(client, headers, nombre="Dos")
    pid = await crear_producto(client, headers)
    p1 = await crear_pedido(client, headers, d1, [(pid, 1)])
    p2 = await crear_pedido(client, headers, d2, [(pid, 1)])
    response = await client.get(
        PEDIDOS_URL, params={"distribuidora_id": d2}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert [p["id"] for p in body["items"]] == [p2["id"]]
    assert p1["id"] not in [p["id"] for p in body["items"]]
    assert body["total"] == 1


async def test_pedido_de_dos_lineas_con_costos_de_origenes_distintos(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    con_lista = await crear_producto(client, headers, sku="CMP-L", costo=1000)
    sin_lista = await crear_producto(client, headers, sku="CMP-S", costo=250)
    await agregar_a_lista(client, headers, did, con_lista, 800)
    pedido = await crear_pedido(client, headers, did, [(con_lista, 2), (sin_lista, 4)])
    costos = {li["producto_id"]: li["costo_unitario"] for li in pedido["lineas"]}
    assert costos == {con_lista: 800, sin_lista: 250}
    assert pedido["total_estimado"] == 2 * 800 + 4 * 250


async def test_cambio_posterior_de_lista_no_altera_el_snapshot(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, costo=1000)
    await agregar_a_lista(client, headers, did, pid, 800)
    pedido = await crear_pedido(client, headers, did, [(pid, 3)])
    cambio = await client.put(
        f"/api/distribuidoras/{did}/listas/{pid}", json={"costo": 900}, headers=headers
    )
    assert cambio.status_code == 200
    detalle = (await client.get(f"{PEDIDOS_URL}/{pedido['id']}", headers=headers)).json()
    assert detalle["lineas"][0]["costo_unitario"] == 800
    assert detalle["total_estimado"] == 2400
    # Un pedido nuevo si toma el costo vigente de la lista.
    nuevo = await crear_pedido(client, headers, did, [(pid, 1)])
    assert nuevo["lineas"][0]["costo_unitario"] == 900
