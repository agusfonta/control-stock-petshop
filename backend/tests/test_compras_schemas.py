"""Validacion de schemas Pydantic de compras (C-07 task 3.1, RED-first).

PedidoCreate (lineas 1..100, cantidad int > 0, producto sin repetir, sin
costo del cliente: D6/D11) y PagoCreate (monto > 0, metodo en lista, sin
pedido_id: RN-CP-03, fecha opcional). Se valida con model_validate sobre
dicts, que es lo que recibe FastAPI del JSON.
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import PagoCreate, PedidoCreate


def _linea(producto_id="p1", cantidad=1, **extra):
    return {"producto_id": producto_id, "cantidad": cantidad, **extra}


def _pedido(**overrides):
    datos = {"distribuidora_id": "d1", "lineas": [_linea()]}
    datos.update(overrides)
    return datos


# --- PedidoCreate ---


def test_pedido_create_ok_minimo() -> None:
    pedido = PedidoCreate.model_validate(_pedido())
    assert pedido.distribuidora_id == "d1"
    assert pedido.notas is None
    assert len(pedido.lineas) == 1
    assert pedido.lineas[0].cantidad == 1


def test_pedido_create_ok_con_notas_y_varias_lineas() -> None:
    pedido = PedidoCreate.model_validate(
        _pedido(lineas=[_linea("p1", 10), _linea("p2", 5)], notas="urgente")
    )
    assert [linea.producto_id for linea in pedido.lineas] == ["p1", "p2"]
    assert pedido.notas == "urgente"


def test_pedido_create_lineas_vacias_rechazadas() -> None:
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(_pedido(lineas=[]))


def test_pedido_create_sin_lineas_rechazado() -> None:
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate({"distribuidora_id": "d1"})


def test_pedido_create_mas_de_100_lineas_rechazado() -> None:
    lineas = [_linea(f"p{i}") for i in range(101)]
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(_pedido(lineas=lineas))


def test_pedido_create_exactamente_100_lineas_ok() -> None:
    lineas = [_linea(f"p{i}") for i in range(100)]
    assert len(PedidoCreate.model_validate(_pedido(lineas=lineas)).lineas) == 100


@pytest.mark.parametrize("cantidad", [0, -1, 1.5, 2.0, "3", True])
def test_pedido_create_cantidad_invalida_rechazada(cantidad) -> None:
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(_pedido(lineas=[_linea(cantidad=cantidad)]))


def test_pedido_create_producto_repetido_rechazado() -> None:
    lineas = [_linea("p1", 1), _linea("p2", 1), _linea("p1", 3)]
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(_pedido(lineas=lineas))


def test_pedido_create_costo_unitario_en_linea_rechazado() -> None:
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(
            _pedido(lineas=[_linea(costo_unitario=800)])
        )


def test_pedido_create_campo_extra_rechazado() -> None:
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(_pedido(estado="recibido"))


def test_pedido_create_distribuidora_vacia_rechazada() -> None:
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(_pedido(distribuidora_id=""))


def test_pedido_create_notas_demasiado_largas_rechazadas() -> None:
    with pytest.raises(ValidationError):
        PedidoCreate.model_validate(_pedido(notas="x" * 501))


# --- PagoCreate ---


def _pago(**overrides):
    datos = {"distribuidora_id": "d1", "monto": 5000, "metodo": "transferencia"}
    datos.update(overrides)
    return datos


def test_pago_create_ok_minimo_fecha_omitida() -> None:
    pago = PagoCreate.model_validate(_pago())
    assert pago.monto == Decimal("5000")
    assert pago.metodo == "transferencia"
    assert pago.fecha is None
    assert pago.nota is None


def test_pago_create_ok_con_fecha_y_nota() -> None:
    pago = PagoCreate.model_validate(_pago(fecha="2026-03-15", nota="cuota 1"))
    assert pago.fecha == date(2026, 3, 15)
    assert pago.nota == "cuota 1"


@pytest.mark.parametrize("metodo", ["efectivo", "transferencia", "cheque", "otro"])
def test_pago_create_metodos_validos(metodo) -> None:
    assert PagoCreate.model_validate(_pago(metodo=metodo)).metodo == metodo


@pytest.mark.parametrize("monto", [0, -1, -0.01, True, "abc"])
def test_pago_create_monto_invalido_rechazado(monto) -> None:
    with pytest.raises(ValidationError):
        PagoCreate.model_validate(_pago(monto=monto))


def test_pago_create_monto_decimal_ok() -> None:
    pago = PagoCreate.model_validate(_pago(monto=1234.5))
    assert pago.monto == Decimal("1234.5")


def test_pago_create_monto_con_mas_de_2_decimales_rechazado() -> None:
    with pytest.raises(ValidationError):
        PagoCreate.model_validate(_pago(monto="10.001"))


def test_pago_create_monto_excede_precision_de_columna_rechazado() -> None:
    with pytest.raises(ValidationError):
        PagoCreate.model_validate(_pago(monto="10000000000.00"))


def test_pago_create_metodo_fuera_de_lista_rechazado() -> None:
    with pytest.raises(ValidationError):
        PagoCreate.model_validate(_pago(metodo="bitcoin"))


def test_pago_create_pedido_id_rechazado() -> None:
    with pytest.raises(ValidationError):
        PagoCreate.model_validate(_pago(pedido_id="ped-1"))


def test_pago_create_fecha_invalida_rechazada() -> None:
    with pytest.raises(ValidationError):
        PagoCreate.model_validate(_pago(fecha="15/03/2026"))


def test_pago_create_sin_distribuidora_rechazado() -> None:
    datos = _pago()
    del datos["distribuidora_id"]
    with pytest.raises(ValidationError):
        PagoCreate.model_validate(datos)
