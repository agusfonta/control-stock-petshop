"""Validacion de schemas Pydantic de ventas (C-10 task 3.1, RED-first).

VentaCreate (idempotency_key UUID, lineas 1..100, cantidad int > 0, producto
sin repetir, sin precio/total del cliente: D5/D8), ConfirmarVentaRequest
(1..5 pagos, monto > 0 con a lo sumo 2 decimales, metodo en lista, ref_mp
opcional no vacio: D10), AnularVentaRequest (motivo 1..300: D13) y el filtro
de listado (estado en lista, desde/hasta con zona: D15). Se valida con
model_validate sobre dicts, que es lo que recibe FastAPI del JSON.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    AnularVentaRequest,
    ConfirmarVentaRequest,
    VentaCreate,
    VentaFiltros,
    VentaResponse,
)


def _linea(producto_id="p1", cantidad=1, **extra):
    return {"producto_id": producto_id, "cantidad": cantidad, **extra}


def _venta(**overrides):
    datos = {"idempotency_key": str(uuid.uuid4()), "lineas": [_linea()]}
    datos.update(overrides)
    return datos


def _pago(metodo="efectivo", monto=100, **extra):
    return {"metodo": metodo, "monto": monto, **extra}


# --- VentaCreate ---


def test_venta_create_ok_minimo_sin_cliente() -> None:
    venta = VentaCreate.model_validate(_venta())
    assert venta.cliente_id is None
    assert len(venta.lineas) == 1
    assert venta.lineas[0].cantidad == 1


def test_venta_create_ok_con_cliente_y_varias_lineas() -> None:
    venta = VentaCreate.model_validate(
        _venta(cliente_id="c1", lineas=[_linea("p1", 2), _linea("p2", 1)])
    )
    assert venta.cliente_id == "c1"
    assert [linea.producto_id for linea in venta.lineas] == ["p1", "p2"]


def test_venta_create_idempotency_key_ausente_rechazada() -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate({"lineas": [_linea()]})


@pytest.mark.parametrize(
    "clave",
    ["", "no-es-uuid", "1234", str(uuid.uuid4()) + "x", str(uuid.uuid4()).replace("-", ""), 123],
)
def test_venta_create_idempotency_key_no_uuid_rechazada(clave) -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(idempotency_key=clave))


def test_venta_create_idempotency_key_uuid_mayusculas_se_normaliza() -> None:
    clave = str(uuid.uuid4())
    venta = VentaCreate.model_validate(_venta(idempotency_key=clave.upper()))
    assert venta.idempotency_key == clave


def test_venta_create_lineas_vacias_rechazadas() -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(lineas=[]))


def test_venta_create_mas_de_100_lineas_rechazado() -> None:
    lineas = [_linea(f"p{i}") for i in range(101)]
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(lineas=lineas))


def test_venta_create_exactamente_100_lineas_ok() -> None:
    lineas = [_linea(f"p{i}") for i in range(100)]
    assert len(VentaCreate.model_validate(_venta(lineas=lineas)).lineas) == 100


@pytest.mark.parametrize("cantidad", [0, -1, 1.5, 2.0, "3", True])
def test_venta_create_cantidad_invalida_rechazada(cantidad) -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(lineas=[_linea(cantidad=cantidad)]))


def test_venta_create_producto_repetido_rechazado() -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(lineas=[_linea("p1", 1), _linea("p1", 2)]))


def test_venta_create_producto_id_vacio_rechazado() -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(lineas=[_linea(producto_id="")]))


def test_venta_create_precio_unit_en_linea_rechazado_por_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(lineas=[_linea(precio_unit=1)]))


@pytest.mark.parametrize("campo", ["total", "subtotal", "estado", "usuario_id"])
def test_venta_create_campo_del_servidor_rechazado_por_extra_forbid(campo) -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(**{campo: 100}))


def test_venta_create_cliente_id_vacio_rechazado() -> None:
    with pytest.raises(ValidationError):
        VentaCreate.model_validate(_venta(cliente_id=""))


# --- ConfirmarVentaRequest ---


def test_confirmar_ok_un_pago() -> None:
    req = ConfirmarVentaRequest.model_validate({"pagos": [_pago()]})
    assert req.pagos[0].metodo == "efectivo"
    assert req.pagos[0].monto == Decimal("100")
    assert req.pagos[0].ref_mp is None


def test_confirmar_ok_pago_mixto_con_ref_mp() -> None:
    req = ConfirmarVentaRequest.model_validate(
        {
            "pagos": [
                _pago("efectivo", 1800),
                _pago("mp", 2000.5, ref_mp="  MP-123  "),
            ]
        }
    )
    assert req.pagos[1].monto == Decimal("2000.5")
    assert req.pagos[1].ref_mp == "MP-123"


def test_confirmar_pagos_vacios_rechazados() -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate({"pagos": []})


def test_confirmar_sin_pagos_rechazado() -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate({})


def test_confirmar_mas_de_5_pagos_rechazado() -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate({"pagos": [_pago() for _ in range(6)]})


def test_confirmar_exactamente_5_pagos_ok() -> None:
    req = ConfirmarVentaRequest.model_validate({"pagos": [_pago() for _ in range(5)]})
    assert len(req.pagos) == 5


@pytest.mark.parametrize("monto", [0, -1, -0.5, 10.123, "10.123", True, "abc"])
def test_confirmar_monto_invalido_rechazado(monto) -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate({"pagos": [_pago(monto=monto)]})


@pytest.mark.parametrize("monto", [1, 0.01, 10.5, "10.50", 9999999999.99])
def test_confirmar_monto_valido_aceptado(monto) -> None:
    req = ConfirmarVentaRequest.model_validate({"pagos": [_pago(monto=monto)]})
    assert req.pagos[0].monto > 0


def test_confirmar_monto_con_mas_de_12_digitos_rechazado() -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate({"pagos": [_pago(monto=10000000000.00)]})


@pytest.mark.parametrize("metodo", ["cheque", "otro", "Efectivo", "", None, 1])
def test_confirmar_metodo_fuera_de_lista_rechazado(metodo) -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate({"pagos": [_pago(metodo=metodo)]})


@pytest.mark.parametrize("metodo", ["efectivo", "transferencia", "mp", "tarjeta"])
def test_confirmar_metodos_validos_aceptados(metodo) -> None:
    req = ConfirmarVentaRequest.model_validate({"pagos": [_pago(metodo=metodo)]})
    assert req.pagos[0].metodo == metodo


@pytest.mark.parametrize("ref_mp", ["", "   "])
def test_confirmar_ref_mp_en_blanco_rechazado(ref_mp) -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate(
            {"pagos": [_pago("mp", ref_mp=ref_mp)]}
        )


def test_confirmar_ref_mp_mayor_a_100_rechazado() -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate(
            {"pagos": [_pago("mp", ref_mp="x" * 101)]}
        )


def test_confirmar_ref_mp_de_100_ok() -> None:
    req = ConfirmarVentaRequest.model_validate(
        {"pagos": [_pago("mp", ref_mp="x" * 100)]}
    )
    assert len(req.pagos[0].ref_mp) == 100


def test_confirmar_campo_extra_en_pago_rechazado() -> None:
    with pytest.raises(ValidationError):
        ConfirmarVentaRequest.model_validate({"pagos": [_pago(vuelto=5)]})


# --- AnularVentaRequest ---


def test_anular_ok_recorta_motivo() -> None:
    req = AnularVentaRequest.model_validate({"motivo": "  cliente se arrepintio "})
    assert req.motivo == "cliente se arrepintio"


def test_anular_motivo_de_300_ok() -> None:
    assert len(AnularVentaRequest.model_validate({"motivo": "m" * 300}).motivo) == 300


@pytest.mark.parametrize("body", [{}, {"motivo": ""}, {"motivo": "   "}, {"motivo": None}])
def test_anular_motivo_ausente_o_en_blanco_rechazado(body) -> None:
    with pytest.raises(ValidationError):
        AnularVentaRequest.model_validate(body)


def test_anular_motivo_mayor_a_300_rechazado() -> None:
    with pytest.raises(ValidationError):
        AnularVentaRequest.model_validate({"motivo": "m" * 301})


# --- Filtros de listado ---


def test_filtros_vacios_ok() -> None:
    filtros = VentaFiltros.model_validate({})
    assert filtros.estado is None
    assert filtros.desde is None
    assert filtros.hasta is None


@pytest.mark.parametrize("estado", ["pagada", "", "Confirmada"])
def test_filtros_estado_invalido_rechazado(estado) -> None:
    with pytest.raises(ValidationError):
        VentaFiltros.model_validate({"estado": estado})


@pytest.mark.parametrize("estado", ["borrador", "confirmada", "anulada"])
def test_filtros_estado_valido_aceptado(estado) -> None:
    assert VentaFiltros.model_validate({"estado": estado}).estado == estado


@pytest.mark.parametrize("campo", ["desde", "hasta"])
def test_filtros_fecha_naive_rechazada(campo) -> None:
    with pytest.raises(ValidationError):
        VentaFiltros.model_validate({campo: "2026-10-05T00:00:00"})


@pytest.mark.parametrize("valor", ["2026-10-05T00:00:00-03:00", "2026-10-05T03:00:00Z"])
def test_filtros_fecha_con_zona_aceptada(valor) -> None:
    filtros = VentaFiltros.model_validate({"desde": valor})
    assert filtros.desde.utcoffset() is not None
    assert filtros.desde == datetime(2026, 10, 5, 3, 0, tzinfo=timezone.utc)


def test_filtros_fecha_basura_rechazada() -> None:
    with pytest.raises(ValidationError):
        VentaFiltros.model_validate({"desde": "ayer"})


def test_filtros_page_size_fuera_de_rango_rechazado() -> None:
    with pytest.raises(ValidationError):
        VentaFiltros.model_validate({"page_size": 101})
    with pytest.raises(ValidationError):
        VentaFiltros.model_validate({"page": 0})


# --- Respuesta ---


def test_venta_response_serializa_dinero_como_numero() -> None:
    ahora = datetime.now(timezone.utc)
    respuesta = VentaResponse.model_validate(
        {
            "id": "v1",
            "estado": "confirmada",
            "cliente_id": None,
            "usuario_id": "u1",
            "total": Decimal("3800.00"),
            "lineas": [
                {
                    "id": "l1",
                    "producto_id": "p1",
                    "producto_nombre": "Alimento",
                    "cantidad": 2,
                    "precio_unit": Decimal("15.05"),
                    "subtotal": Decimal("30.10"),
                }
            ],
            "pagos": [
                {
                    "id": "g1",
                    "metodo": "efectivo",
                    "monto": Decimal("3800.00"),
                    "ref_mp": None,
                    "created_at": ahora,
                }
            ],
            "created_at": ahora,
            "confirmada_at": ahora + timedelta(seconds=1),
            "confirmada_por_id": "u1",
            "anulada_at": None,
            "anulada_por_id": None,
            "motivo_anulacion": None,
        }
    )
    cuerpo = respuesta.model_dump(mode="json")
    assert cuerpo["total"] == 3800 and isinstance(cuerpo["total"], int)
    assert cuerpo["lineas"][0]["precio_unit"] == 15.05
    assert cuerpo["lineas"][0]["subtotal"] == 30.1
    assert cuerpo["pagos"][0]["monto"] == 3800


def test_venta_response_estado_fuera_de_lista_rechazado() -> None:
    with pytest.raises(ValidationError):
        VentaResponse.model_validate(
            {
                "id": "v1",
                "estado": "pagada",
                "cliente_id": None,
                "usuario_id": "u1",
                "total": Decimal("1"),
                "lineas": [],
                "pagos": [],
                "created_at": datetime.now(timezone.utc),
                "confirmada_at": None,
                "confirmada_por_id": None,
                "anulada_at": None,
                "anulada_por_id": None,
                "motivo_anulacion": None,
            }
        )
