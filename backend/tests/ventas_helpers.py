"""Helpers compartidos por los tests de ventas (C-10). No es un modulo de tests."""

import uuid

from tests.compras_helpers import (  # noqa: F401  (re-export para los tests)
    PRODUCTOS_URL,
    contar,
    crear_producto,
    get_producto,
    login_duena,
    login_mostrador,
    movimientos_de,
)

VENTAS_URL = "/api/ventas"
CLIENTES_URL = "/api/clientes"


def clave_nueva() -> str:
    return str(uuid.uuid4())


async def crear_cliente(client, headers, nombre="Ana Perez") -> str:
    response = await client.post(CLIENTES_URL, json={"nombre": nombre}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def usuario_id(client, headers) -> str:
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


async def post_venta(client, headers, lineas, cliente_id=None, clave=None, **extra):
    """POST crudo (devuelve la response) para poder afirmar sobre errores."""
    body = {
        "idempotency_key": clave or clave_nueva(),
        "lineas": [{"producto_id": p, "cantidad": c} for p, c in lineas],
        **extra,
    }
    if cliente_id is not None:
        body["cliente_id"] = cliente_id
    return await client.post(VENTAS_URL, json=body, headers=headers)


async def crear_venta(client, headers, lineas, **kwargs) -> dict:
    response = await post_venta(client, headers, lineas, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()


def pago(metodo="efectivo", monto=100, **extra) -> dict:
    return {"metodo": metodo, "monto": monto, **extra}


async def post_confirmar(client, headers, venta_id, pagos):
    """POST crudo de confirmar (devuelve la response)."""
    return await client.post(
        f"{VENTAS_URL}/{venta_id}/confirmar", json={"pagos": pagos}, headers=headers
    )


async def confirmar_venta(client, headers, venta_id, pagos) -> dict:
    response = await post_confirmar(client, headers, venta_id, pagos)
    assert response.status_code == 200, response.text
    return response.json()


async def post_anular(client, headers, venta_id, motivo="cliente se arrepintio"):
    return await client.post(
        f"{VENTAS_URL}/{venta_id}/anular", json={"motivo": motivo}, headers=headers
    )


async def get_venta(client, headers, venta_id) -> dict:
    response = await client.get(f"{VENTAS_URL}/{venta_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def venta_confirmada(client, headers, lineas, pagos, **kwargs) -> dict:
    """Crea un borrador y lo confirma con `pagos`; devuelve la venta confirmada."""
    borrador = await crear_venta(client, headers, lineas, **kwargs)
    return await confirmar_venta(client, headers, borrador["id"], pagos)
