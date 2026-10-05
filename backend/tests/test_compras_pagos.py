"""Pagos a distribuidoras independientes de pedidos (C-07 task 7.1, RED-first).

POST/GET /api/compras/pagos y DELETE /api/compras/pagos/{id}, solo duena
(D8). Un pago no referencia ni modifica pedidos ni stock (RN-CP-03);
anular = soft-delete. En RED fallan: los endpoints de pagos no existen.
"""

from datetime import date

from tests.compras_helpers import (
    PAGOS_URL,
    PEDIDOS_URL,
    contar,
    crear_distribuidora,
    crear_pedido,
    crear_producto,
    get_producto,
    login_duena,
    login_mostrador,
)


def _pago(distribuidora_id: str, **overrides) -> dict:
    body = {"distribuidora_id": distribuidora_id, "monto": 5000, "metodo": "transferencia"}
    body.update(overrides)
    return body


async def test_pago_201_sin_pedidos_fecha_hoy_y_sin_tocar_nada(
    client, db_session_factory
) -> None:
    from app.models import MovimientoStock, PedidoCompra

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    response = await client.post(PAGOS_URL, json=_pago(did), headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["distribuidora_id"] == did
    assert body["monto"] == 5000
    assert body["metodo"] == "transferencia"
    assert body["fecha"] == date.today().isoformat()
    assert body["activo"] is True
    assert body["nota"] is None
    assert contar(db_session_factory, PedidoCompra) == 0
    assert contar(db_session_factory, MovimientoStock) == 0


async def test_pago_con_pedido_existente_no_toca_pedido_ni_stock(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, stock_actual=3)
    pedido = await crear_pedido(client, headers, did, [(pid, 10)])
    response = await client.post(PAGOS_URL, json=_pago(did, monto=9000), headers=headers)
    assert response.status_code == 201
    detalle = (await client.get(f"{PEDIDOS_URL}/{pedido['id']}", headers=headers)).json()
    assert detalle["estado"] == "pendiente"
    assert (await get_producto(client, headers, pid))["stock_actual"] == 3


async def test_pago_monto_cero_o_negativo_422(client, db_session_factory) -> None:
    from app.models import PagoDistribuidora

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    for monto in (0, -100):
        response = await client.post(
            PAGOS_URL, json=_pago(did, monto=monto), headers=headers
        )
        assert response.status_code == 422
    assert contar(db_session_factory, PagoDistribuidora) == 0


async def test_pago_metodo_invalido_422(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    response = await client.post(
        PAGOS_URL, json=_pago(did, metodo="bitcoin"), headers=headers
    )
    assert response.status_code == 422


async def test_pago_con_pedido_id_422(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    response = await client.post(
        PAGOS_URL, json=_pago(did, pedido_id="cualquiera"), headers=headers
    )
    assert response.status_code == 422


async def test_pago_distribuidora_inexistente_404(client, db_session_factory) -> None:
    from app.models import PagoDistribuidora

    headers = await login_duena(client)
    response = await client.post(PAGOS_URL, json=_pago("no-existe"), headers=headers)
    assert response.status_code == 404
    assert "distribuidora" in response.json()["detail"]
    assert contar(db_session_factory, PagoDistribuidora) == 0


async def test_pago_a_distribuidora_inactiva_201(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    assert (
        await client.delete(f"/api/distribuidoras/{did}", headers=headers)
    ).status_code == 204
    response = await client.post(PAGOS_URL, json=_pago(did), headers=headers)
    assert response.status_code == 201


async def test_mostrador_403_en_post_get_y_delete(client, db_session_factory) -> None:
    from app.models import PagoDistribuidora

    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    did = await crear_distribuidora(client, duena)
    pago = (await client.post(PAGOS_URL, json=_pago(did), headers=duena)).json()
    assert (
        await client.post(PAGOS_URL, json=_pago(did), headers=mostrador)
    ).status_code == 403
    assert (await client.get(PAGOS_URL, headers=mostrador)).status_code == 403
    assert (
        await client.delete(f"{PAGOS_URL}/{pago['id']}", headers=mostrador)
    ).status_code == 403
    assert contar(db_session_factory, PagoDistribuidora) == 1
    activos = (await client.get(PAGOS_URL, headers=duena)).json()["total"]
    assert activos == 1


async def test_pago_anonimo_401(client) -> None:
    assert (
        await client.post(PAGOS_URL, json=_pago("cualquiera"))
    ).status_code == 401
    assert (await client.get(PAGOS_URL)).status_code == 401
    assert (await client.delete(f"{PAGOS_URL}/cualquiera")).status_code == 401


async def test_listar_pagos_filtra_por_distribuidora(client) -> None:
    headers = await login_duena(client)
    d1 = await crear_distribuidora(client, headers, nombre="Uno")
    d2 = await crear_distribuidora(client, headers, nombre="Dos")
    p1 = (await client.post(PAGOS_URL, json=_pago(d1), headers=headers)).json()
    p2 = (await client.post(PAGOS_URL, json=_pago(d2, monto=700), headers=headers)).json()
    todos = (await client.get(PAGOS_URL, headers=headers)).json()
    assert {p["id"] for p in todos["items"]} == {p1["id"], p2["id"]}
    assert (todos["page"], todos["page_size"], todos["total_pages"]) == (1, 20, 1)
    filtrados = (
        await client.get(PAGOS_URL, params={"distribuidora_id": d2}, headers=headers)
    ).json()
    assert [p["id"] for p in filtrados["items"]] == [p2["id"]]
    assert filtrados["total"] == 1


async def test_anular_pago_204_soft_delete_y_deja_de_listarse(
    client, db_session_factory
) -> None:
    from app.models import PagoDistribuidora

    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pago = (await client.post(PAGOS_URL, json=_pago(did), headers=headers)).json()
    response = await client.delete(f"{PAGOS_URL}/{pago['id']}", headers=headers)
    assert response.status_code == 204
    listado = (await client.get(PAGOS_URL, headers=headers)).json()
    assert listado["items"] == []
    assert listado["total"] == 0
    with db_session_factory() as session:
        fila = session.get(PagoDistribuidora, pago["id"])
        assert fila is not None
        assert fila.activo is False


async def test_anular_pago_inexistente_404(client) -> None:
    headers = await login_duena(client)
    response = await client.delete(f"{PAGOS_URL}/no-existe", headers=headers)
    assert response.status_code == 404
    assert "pago" in response.json()["detail"]


# --- Triangulacion (7.3) ---


async def test_fecha_explicita_pasada_se_respeta(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    response = await client.post(
        PAGOS_URL,
        json=_pago(did, fecha="2026-01-15", nota="cuota enero"),
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["fecha"] == "2026-01-15"
    assert body["nota"] == "cuota enero"
    listado = (await client.get(PAGOS_URL, headers=headers)).json()
    assert listado["items"][0]["fecha"] == "2026-01-15"


async def test_fecha_con_formato_invalido_422(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    response = await client.post(
        PAGOS_URL, json=_pago(did, fecha="15/01/2026"), headers=headers
    )
    assert response.status_code == 422


async def test_pago_con_pedido_pendiente_no_cambia_su_estado_ni_su_recepcion(
    client,
) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    pid = await crear_producto(client, headers, stock_actual=1)
    pedido = await crear_pedido(client, headers, did, [(pid, 4)])
    await client.post(PAGOS_URL, json=_pago(did, monto=100), headers=headers)
    antes = (await client.get(f"{PEDIDOS_URL}/{pedido['id']}", headers=headers)).json()
    assert antes["estado"] == "pendiente"
    assert antes["entradas"] == []
    # El pedido sigue recibiendose normalmente; el pago no lo condiciona.
    recibido = await client.post(f"{PEDIDOS_URL}/{pedido['id']}/recibir", headers=headers)
    assert recibido.status_code == 200
    assert (await get_producto(client, headers, pid))["stock_actual"] == 5
