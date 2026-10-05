"""Helpers compartidos por los tests de compras (C-07). No es un modulo de tests."""

from tests.conftest import (
    DUENA_EMAIL,
    DUENA_PASSWORD,
    MOSTRADOR_EMAIL,
    MOSTRADOR_PASSWORD,
)

PEDIDOS_URL = "/api/compras/pedidos"
PAGOS_URL = "/api/compras/pagos"
DISTRIBUIDORAS_URL = "/api/distribuidoras"
PRODUCTOS_URL = "/api/productos"


async def login(client, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def login_duena(client) -> dict:
    return await login(client, DUENA_EMAIL, DUENA_PASSWORD)


async def login_mostrador(client) -> dict:
    return await login(client, MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD)


async def crear_distribuidora(client, headers, nombre="Distri Sur") -> str:
    response = await client.post(
        DISTRIBUIDORAS_URL, json={"nombre": nombre}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


async def crear_producto(
    client,
    headers,
    sku="CMP-001",
    costo=1000,
    margen_pct=0.5,
    stock_actual=0,
) -> str:
    response = await client.post(
        PRODUCTOS_URL,
        json={
            "sku": sku,
            "nombre": f"Producto {sku}",
            "costo": costo,
            "margen_pct": margen_pct,
            "stock_actual": stock_actual,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def agregar_a_lista(client, headers, distribuidora_id, producto_id, costo):
    response = await client.post(
        f"{DISTRIBUIDORAS_URL}/{distribuidora_id}/listas",
        json={"producto_id": producto_id, "costo": costo},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def post_pedido(client, headers, distribuidora_id, lineas, **extra):
    """POST crudo (devuelve la response) para poder afirmar sobre errores."""
    body = {
        "distribuidora_id": distribuidora_id,
        "lineas": [{"producto_id": p, "cantidad": c} for p, c in lineas],
        **extra,
    }
    return await client.post(PEDIDOS_URL, json=body, headers=headers)


async def crear_pedido(client, headers, distribuidora_id, lineas, **extra) -> dict:
    response = await post_pedido(client, headers, distribuidora_id, lineas, **extra)
    assert response.status_code == 201, response.text
    return response.json()


async def get_producto(client, headers, producto_id) -> dict:
    response = await client.get(f"{PRODUCTOS_URL}/{producto_id}", headers=headers)
    assert response.status_code == 200
    return response.json()


def movimientos_de(db_session_factory, producto_id: str) -> list:
    from app.models import MovimientoStock

    with db_session_factory() as session:
        return (
            session.query(MovimientoStock)
            .filter_by(producto_id=producto_id)
            .order_by(MovimientoStock.created_at.asc())
            .all()
        )


def contar(db_session_factory, modelo) -> int:
    with db_session_factory() as session:
        return session.query(modelo).count()
