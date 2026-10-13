"""Cuenta simple por distribuidora (C-07 task 8.1, RED-first).

GET /api/compras/distribuidoras/{id}/cuenta, solo duena: total_recibido
(entradas de pedidos recibidos) - total_pagado (pagos activos) = saldo,
calculado al vuelo (D10). En RED fallan: el endpoint no existe.
"""

from tests.compras_helpers import (
    PAGOS_URL,
    PEDIDOS_URL,
    agregar_a_lista,
    crear_distribuidora,
    crear_pedido,
    crear_producto,
    login_duena,
    login_mostrador,
)


def _cuenta_url(distribuidora_id: str) -> str:
    return f"/api/compras/distribuidoras/{distribuidora_id}/cuenta"


async def _pagar(client, headers, distribuidora_id, monto) -> dict:
    response = await client.post(
        PAGOS_URL,
        json={
            "distribuidora_id": distribuidora_id,
            "monto": monto,
            "metodo": "efectivo",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def _recibir(client, headers, pedido_id) -> None:
    response = await client.post(f"{PEDIDOS_URL}/{pedido_id}/recibir", headers=headers)
    assert response.status_code == 200


async def test_saldo_con_entradas_pendientes_y_pagos_activos_y_anulados(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="CTA-A", costo=1000)
    b = await crear_producto(client, headers, sku="CTA-B", costo=200)
    await agregar_a_lista(client, headers, did, a, 800)
    recibido = await crear_pedido(client, headers, did, [(a, 10), (b, 5)])  # 9000
    await _recibir(client, headers, recibido["id"])
    await crear_pedido(client, headers, did, [(a, 5)])  # pendiente: 4000, no suma
    await _pagar(client, headers, did, 3000)
    await _pagar(client, headers, did, 2000)
    anulado = await _pagar(client, headers, did, 1000)
    assert (
        await client.delete(f"{PAGOS_URL}/{anulado['id']}", headers=headers)
    ).status_code == 204

    response = await client.get(_cuenta_url(did), headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "distribuidora_id": did,
        "total_recibido": 9000,
        "total_pagado": 5000,
        "saldo": 4000,
    }


async def test_distribuidora_sin_movimientos_todo_en_cero(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    response = await client.get(_cuenta_url(did), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert (body["total_recibido"], body["total_pagado"], body["saldo"]) == (0, 0, 0)


async def test_cuenta_de_distribuidora_inexistente_404(client) -> None:
    headers = await login_duena(client)
    response = await client.get(_cuenta_url("no-existe"), headers=headers)
    assert response.status_code == 404
    assert "distribuidora" in response.json()["detail"]


async def test_mostrador_no_ve_la_cuenta_403(client) -> None:
    duena = await login_duena(client)
    mostrador = await login_mostrador(client)
    did = await crear_distribuidora(client, duena)
    assert (await client.get(_cuenta_url(did), headers=mostrador)).status_code == 403


async def test_cuenta_anonimo_401(client) -> None:
    assert (await client.get(_cuenta_url("cualquiera"))).status_code == 401


# --- Triangulacion (8.3) ---


async def test_pedido_cancelado_no_suma_al_total_recibido(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="CTA-C", costo=1000)
    cancelado = await crear_pedido(client, headers, did, [(a, 5)])
    cancelar = await client.post(
        f"{PEDIDOS_URL}/{cancelado['id']}/cancelar", headers=headers
    )
    assert cancelar.status_code == 200
    body = (await client.get(_cuenta_url(did), headers=headers)).json()
    assert (body["total_recibido"], body["total_pagado"], body["saldo"]) == (0, 0, 0)


async def test_saldo_negativo_cuando_se_pago_de_mas(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="CTA-D", costo=900)
    pedido = await crear_pedido(client, headers, did, [(a, 10)])  # 9000
    await _recibir(client, headers, pedido["id"])
    await _pagar(client, headers, did, 10000)
    body = (await client.get(_cuenta_url(did), headers=headers)).json()
    assert (body["total_recibido"], body["total_pagado"], body["saldo"]) == (
        9000,
        10000,
        -1000,
    )


async def test_cuenta_mantiene_los_centavos_sin_ruido_binario(client) -> None:
    headers = await login_duena(client)
    did = await crear_distribuidora(client, headers)
    a = await crear_producto(client, headers, sku="CTA-E", costo=99.99)
    pedido = await crear_pedido(client, headers, did, [(a, 3)])
    await _recibir(client, headers, pedido["id"])
    await _pagar(client, headers, did, 100.1)
    body = (await client.get(_cuenta_url(did), headers=headers)).json()
    assert body["total_recibido"] == 299.97
    assert body["total_pagado"] == 100.1
    assert body["saldo"] == 199.87


async def test_cuenta_no_mezcla_distribuidoras(client) -> None:
    headers = await login_duena(client)
    d1 = await crear_distribuidora(client, headers, nombre="Uno")
    d2 = await crear_distribuidora(client, headers, nombre="Dos")
    a = await crear_producto(client, headers, sku="CTA-F", costo=100)
    pedido = await crear_pedido(client, headers, d1, [(a, 2)])
    await _recibir(client, headers, pedido["id"])
    await _pagar(client, headers, d2, 50)
    cuenta1 = (await client.get(_cuenta_url(d1), headers=headers)).json()
    cuenta2 = (await client.get(_cuenta_url(d2), headers=headers)).json()
    assert (cuenta1["total_recibido"], cuenta1["total_pagado"], cuenta1["saldo"]) == (200, 0, 200)
    assert (cuenta2["total_recibido"], cuenta2["total_pagado"], cuenta2["saldo"]) == (0, 50, -50)
