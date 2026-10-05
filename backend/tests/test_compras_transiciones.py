"""Transiciones de estado y cancelacion (C-07 task 6.1, RED-first).

Solo pendiente -> recibido y pendiente -> cancelado; los estados finales
responden 409 sin efectos y un pedido nunca suma stock dos veces (D7).
Cancelar es exclusivo de la duena. En RED fallan: el endpoint cancelar no
existe.
"""

from tests.compras_helpers import (
    PEDIDOS_URL,
    contar,
    crear_distribuidora,
    crear_pedido,
    crear_producto,
    get_producto,
    login_duena,
    login_mostrador,
    movimientos_de,
)


def _recibir(pedido_id: str) -> str:
    return f"{PEDIDOS_URL}/{pedido_id}/recibir"


def _cancelar(pedido_id: str) -> str:
    return f"{PEDIDOS_URL}/{pedido_id}/cancelar"


async def _pedido_simple(client, headers, stock=3, cantidad=10):
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, costo=1000, stock_actual=stock)
    pedido = await crear_pedido(client, headers, did, [(pid, cantidad)])
    return pid, pedido


def _efectos(db_session_factory) -> tuple[int, int]:
    from app.models import EntradaStock, MovimientoStock

    return (
        contar(db_session_factory, EntradaStock),
        contar(db_session_factory, MovimientoStock),
    )


async def test_recibir_dos_veces_200_luego_409_sin_duplicar(
    client, db_session_factory
) -> None:
    headers = await login_duena(client)
    pid, pedido = await _pedido_simple(client, headers)
    primera = await client.post(_recibir(pedido["id"]), headers=headers)
    assert primera.status_code == 200
    tras_primera = (
        (await get_producto(client, headers, pid))["stock_actual"],
        _efectos(db_session_factory),
    )
    assert tras_primera == (13, (1, 1))
    segunda = await client.post(_recibir(pedido["id"]), headers=headers)
    assert segunda.status_code == 409
    tras_segunda = (
        (await get_producto(client, headers, pid))["stock_actual"],
        _efectos(db_session_factory),
    )
    assert tras_segunda == tras_primera
    assert len(movimientos_de(db_session_factory, pid)) == 1


async def test_recibir_cancelado_409_sin_cambios(client, db_session_factory) -> None:
    headers = await login_duena(client)
    pid, pedido = await _pedido_simple(client, headers)
    assert (await client.post(_cancelar(pedido["id"]), headers=headers)).status_code == 200
    response = await client.post(_recibir(pedido["id"]), headers=headers)
    assert response.status_code == 409
    assert (await get_producto(client, headers, pid))["stock_actual"] == 3
    assert _efectos(db_session_factory) == (0, 0)
    detalle = (await client.get(f"{PEDIDOS_URL}/{pedido['id']}", headers=headers)).json()
    assert detalle["estado"] == "cancelado"


async def test_duena_cancela_pendiente_200_sin_mover_stock(
    client, db_session_factory
) -> None:
    headers = await login_duena(client)
    pid, pedido = await _pedido_simple(client, headers)
    response = await client.post(_cancelar(pedido["id"]), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["estado"] == "cancelado"
    assert body["id"] == pedido["id"]
    assert body["recibido_at"] is None
    assert (await get_producto(client, headers, pid))["stock_actual"] == 3
    assert _efectos(db_session_factory) == (0, 0)
    assert (await get_producto(client, headers, pid))["costo"] == 1000


async def test_cancelar_recibido_409_sin_cambios(client, db_session_factory) -> None:
    headers = await login_duena(client)
    pid, pedido = await _pedido_simple(client, headers)
    assert (await client.post(_recibir(pedido["id"]), headers=headers)).status_code == 200
    response = await client.post(_cancelar(pedido["id"]), headers=headers)
    assert response.status_code == 409
    detalle = (await client.get(f"{PEDIDOS_URL}/{pedido['id']}", headers=headers)).json()
    assert detalle["estado"] == "recibido"
    assert (await get_producto(client, headers, pid))["stock_actual"] == 13
    assert _efectos(db_session_factory) == (1, 1)


async def test_cancelar_cancelado_409(client) -> None:
    headers = await login_duena(client)
    _, pedido = await _pedido_simple(client, headers)
    assert (await client.post(_cancelar(pedido["id"]), headers=headers)).status_code == 200
    assert (await client.post(_cancelar(pedido["id"]), headers=headers)).status_code == 409


async def test_mostrador_no_puede_cancelar_403(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    _, pedido = await _pedido_simple(client, duena)
    response = await client.post(_cancelar(pedido["id"]), headers=mostrador)
    assert response.status_code == 403
    detalle = (await client.get(f"{PEDIDOS_URL}/{pedido['id']}", headers=duena)).json()
    assert detalle["estado"] == "pendiente"


async def test_cancelar_anonimo_401(client) -> None:
    assert (await client.post(_cancelar("cualquiera"))).status_code == 401


async def test_cancelar_inexistente_404(client) -> None:
    headers = await login_duena(client)
    response = await client.post(_cancelar("no-existe"), headers=headers)
    assert response.status_code == 404
    assert "pedido" in response.json()["detail"]


# --- Triangulacion (6.3): barrera de base contra la doble recepcion ---


async def test_barrera_de_base_entrada_preexistente_409_y_rollback_total(
    client, db_session_factory
) -> None:
    from app.models import EntradaStock, MovimientoStock, PedidoCompra, Usuario

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="BAR-A", stock_actual=3)
    b = await crear_producto(client, headers, sku="BAR-B", stock_actual=0)
    pedido = await crear_pedido(client, headers, did, [(a, 10), (b, 4)])
    # Una entrada "fantasma" para el producto que se procesa ULTIMO (orden por
    # id): la primera linea ya se aplico cuando la base rechaza la segunda.
    ultimo = max(a, b)
    with db_session_factory() as session:
        uid = session.query(Usuario).first().id
        session.add(
            EntradaStock(
                pedido_id=pedido["id"],
                producto_id=ultimo,
                cantidad=1,
                costo_unitario=1000,
                usuario_id=uid,
            )
        )
        session.commit()

    response = await client.post(_recibir(pedido["id"]), headers=headers)
    assert response.status_code == 409

    assert (await get_producto(client, headers, a))["stock_actual"] == 3
    assert (await get_producto(client, headers, b))["stock_actual"] == 0
    assert contar(db_session_factory, MovimientoStock) == 0
    assert contar(db_session_factory, EntradaStock) == 1  # solo la preexistente
    with db_session_factory() as session:
        assert session.get(PedidoCompra, pedido["id"]).estado == "pendiente"
