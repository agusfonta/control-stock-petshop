"""Schemas de reportes (C-14 task 4.1, RED-first, D6/D13).

Modelos de query (llegan como query string: fechas ISO estrictas, periodo
validado, parametros desconocidos prohibidos) y de respuesta (estrictos,
dinero como numero con a lo sumo 2 decimales, margen_pct con 4 decimales).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

HOY = date(2026, 10, 6)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """Los defaults de periodo dependen de hoy(): reloj fijo en 2026-10-06."""
    from app.services import reportes

    monkeypatch.setattr(
        reportes, "_ahora_utc", lambda: datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    )


# --- Fechas ISO estrictas ---


@pytest.mark.parametrize(
    "valor",
    [
        "06/10/2026",
        "2026-10-06T10:00:00",
        "2026-10-06T00:00:00",
        "2026-10-06 ",
        "20261006",
        "2026-13-01",
        "ayer",
    ],
)
def test_fecha_con_formato_no_iso_o_con_hora_es_error(valor: str) -> None:
    from app.schemas import VentasDiaQuery

    with pytest.raises(ValidationError):
        VentasDiaQuery.model_validate({"fecha": valor})


@pytest.mark.parametrize("campo", ["desde", "hasta"])
@pytest.mark.parametrize("valor", ["06/10/2026", "2026-10-06T10:00:00"])
def test_desde_y_hasta_no_iso_son_error(campo: str, valor: str) -> None:
    from app.schemas import PeriodoQuery

    with pytest.raises(ValidationError):
        PeriodoQuery.model_validate({campo: valor})


def test_ventas_dia_fecha_iso_y_default_hoy() -> None:
    from app.schemas import VentasDiaQuery

    assert VentasDiaQuery.model_validate({"fecha": "2026-10-05"}).fecha == date(2026, 10, 5)
    assert VentasDiaQuery.model_validate({}).fecha == HOY


# --- Periodo ---


def test_periodo_sin_parametros_es_los_ultimos_30_dias() -> None:
    from app.schemas import PeriodoQuery

    q = PeriodoQuery.model_validate({})
    assert (q.desde, q.hasta) == (date(2026, 9, 7), HOY)


def test_periodo_con_un_solo_borde_completa_el_otro() -> None:
    from app.schemas import PeriodoQuery

    solo_desde = PeriodoQuery.model_validate({"desde": "2026-10-01"})
    assert (solo_desde.desde, solo_desde.hasta) == (date(2026, 10, 1), HOY)
    solo_hasta = PeriodoQuery.model_validate({"hasta": "2026-09-30"})
    assert (solo_hasta.desde, solo_hasta.hasta) == (date(2026, 9, 1), date(2026, 9, 30))


def test_periodo_invertido_es_error() -> None:
    from app.schemas import PeriodoQuery

    with pytest.raises(ValidationError):
        PeriodoQuery.model_validate({"desde": "2026-10-06", "hasta": "2026-10-01"})


def test_periodo_de_367_dias_es_error_y_de_366_es_valido() -> None:
    from app.schemas import PeriodoQuery

    ok = PeriodoQuery.model_validate({"desde": "2025-10-06", "hasta": "2026-10-06"})
    assert (ok.hasta - ok.desde).days == 365
    with pytest.raises(ValidationError):
        PeriodoQuery.model_validate({"desde": "2025-10-05", "hasta": "2026-10-06"})


# --- Rangos y defaults de cada reporte ---


def test_mas_vendidos_defaults_y_orden_monto() -> None:
    from app.schemas import MasVendidosQuery

    q = MasVendidosQuery.model_validate({})
    assert (q.orden, q.limite) == ("cantidad", 10)
    assert MasVendidosQuery.model_validate({"orden": "monto", "limite": "50"}).limite == 50


@pytest.mark.parametrize(
    "params",
    [
        {"orden": "ganancia"},
        {"limite": "0"},
        {"limite": "51"},
        {"limite": "diez"},
    ],
)
def test_mas_vendidos_fuera_de_rango_es_error(params: dict) -> None:
    from app.schemas import MasVendidosQuery

    with pytest.raises(ValidationError):
        MasVendidosQuery.model_validate(params)


def test_reposicion_defaults_y_limites() -> None:
    from app.schemas import ReposicionQuery

    q = ReposicionQuery.model_validate({})
    assert (q.dias, q.cobertura_max_dias) == (30, 7)
    q = ReposicionQuery.model_validate({"dias": "7", "cobertura_max_dias": "1"})
    assert (q.dias, q.cobertura_max_dias) == (7, 1)
    q = ReposicionQuery.model_validate({"dias": "180", "cobertura_max_dias": "90"})
    assert (q.dias, q.cobertura_max_dias) == (180, 90)


@pytest.mark.parametrize(
    "params",
    [
        {"dias": "6"},
        {"dias": "181"},
        {"cobertura_max_dias": "0"},
        {"cobertura_max_dias": "91"},
    ],
)
def test_reposicion_fuera_de_rango_es_error(params: dict) -> None:
    from app.schemas import ReposicionQuery

    with pytest.raises(ValidationError):
        ReposicionQuery.model_validate(params)


def test_margenes_defaults_y_limites_de_paginacion() -> None:
    from app.schemas import MargenesQuery

    q = MargenesQuery.model_validate({})
    assert (q.page, q.page_size) == (1, 20)
    assert MargenesQuery.model_validate({"page_size": "100"}).page_size == 100


@pytest.mark.parametrize("params", [{"page_size": "101"}, {"page_size": "0"}, {"page": "0"}])
def test_margenes_paginacion_fuera_de_rango_es_error(params: dict) -> None:
    from app.schemas import MargenesQuery

    with pytest.raises(ValidationError):
        MargenesQuery.model_validate(params)


@pytest.mark.parametrize(
    "modelo",
    ["VentasDiaQuery", "PeriodoQuery", "MasVendidosQuery", "ReposicionQuery", "MargenesQuery"],
)
def test_parametro_desconocido_es_error(modelo: str) -> None:
    import app.schemas as schemas

    with pytest.raises(ValidationError):
        getattr(schemas, modelo).model_validate({"vendedor": "x"})


# --- Respuestas ---


def _ventas_dia(**cambios):
    from app.schemas import AnuladasResumen, MetodoTotal, VentasDiaResponse

    datos = dict(
        fecha=HOY,
        alcance="todas",
        cantidad_ventas=2,
        total_vendido=Decimal("5300.00"),
        ticket_promedio=Decimal("2650.50"),
        unidades_vendidas=4,
        por_metodo=[
            MetodoTotal(metodo="efectivo", monto=Decimal("4300.00"), cantidad_pagos=2),
            MetodoTotal(metodo="transferencia", monto=Decimal("0"), cantidad_pagos=0),
            MetodoTotal(metodo="mp", monto=Decimal("1000"), cantidad_pagos=1),
            MetodoTotal(metodo="tarjeta", monto=Decimal("0"), cantidad_pagos=0),
        ],
        anuladas=AnuladasResumen(cantidad=1, total=Decimal("1500")),
    )
    datos.update(cambios)
    return VentasDiaResponse(**datos)


def test_ventas_dia_serializa_dinero_como_numero_sin_ceros_de_mas() -> None:
    cuerpo = _ventas_dia().model_dump(mode="json")
    assert cuerpo["fecha"] == "2026-10-06"
    assert cuerpo["total_vendido"] == 5300 and isinstance(cuerpo["total_vendido"], int)
    assert cuerpo["ticket_promedio"] == 2650.5
    assert cuerpo["por_metodo"][0] == {
        "metodo": "efectivo",
        "monto": 4300,
        "cantidad_pagos": 2,
    }
    assert cuerpo["anuladas"] == {"cantidad": 1, "total": 1500}


def test_dinero_con_mas_de_dos_decimales_es_error() -> None:
    with pytest.raises(ValidationError):
        _ventas_dia(total_vendido=Decimal("5300.005"))


def test_ventas_dia_rechaza_alcance_y_metodo_desconocidos() -> None:
    from app.schemas import MetodoTotal

    with pytest.raises(ValidationError):
        _ventas_dia(alcance="otras")
    with pytest.raises(ValidationError):
        MetodoTotal(metodo="cheque", monto=Decimal("1"), cantidad_pagos=1)


def test_respuesta_con_campo_extra_es_error() -> None:
    with pytest.raises(ValidationError):
        _ventas_dia(costo=Decimal("1"))


def _margenes_totales(**cambios):
    from app.schemas import MargenesTotales

    datos = dict(
        ingresos=Decimal("4800"),
        costo=Decimal("3200"),
        margen_bruto=Decimal("1600"),
        margen_pct=Decimal("0.5"),
        lineas_sin_costo=0,
        ingresos_sin_costo=Decimal("0"),
    )
    datos.update(cambios)
    return MargenesTotales(**datos)


def test_margen_pct_se_serializa_con_hasta_4_decimales_o_null() -> None:
    assert _margenes_totales().model_dump(mode="json")["margen_pct"] == 0.5
    assert (
        _margenes_totales(margen_pct=Decimal("0.3333")).model_dump(mode="json")["margen_pct"]
        == 0.3333
    )
    assert _margenes_totales(margen_pct=None).model_dump(mode="json")["margen_pct"] is None


def test_margen_pct_con_mas_de_4_decimales_es_error() -> None:
    with pytest.raises(ValidationError):
        _margenes_totales(margen_pct=Decimal("0.33333"))


def test_margenes_response_hereda_la_paginacion_y_arma_el_envelope() -> None:
    from app.schemas import MargenesResponse, MargenProducto

    item = MargenProducto(
        producto_id="p1",
        sku="A-1",
        nombre="Alimento",
        unidades=3,
        ingresos=Decimal("4800"),
        costo=Decimal("3200"),
        margen_bruto=Decimal("1600"),
        margen_pct=Decimal("0.5"),
    )
    cuerpo = MargenesResponse(
        desde=date(2026, 9, 7),
        hasta=HOY,
        totales=_margenes_totales(),
        total=1,
        page=1,
        page_size=20,
        total_pages=1,
        items=[item],
    ).model_dump(mode="json")
    assert set(cuerpo) == {
        "desde",
        "hasta",
        "totales",
        "total",
        "page",
        "page_size",
        "total_pages",
        "items",
    }
    assert cuerpo["items"][0]["margen_bruto"] == 1600


def test_mas_vendidos_y_reposicion_response_serializan() -> None:
    from app.schemas import (
        MasVendidosResponse,
        ProductoVendido,
        ReposicionItem,
        ReposicionResponse,
    )

    mas = MasVendidosResponse(
        desde=date(2026, 9, 7),
        hasta=HOY,
        orden="cantidad",
        items=[
            ProductoVendido(
                producto_id="p1",
                sku="A-1",
                nombre="Alimento",
                activo=False,
                unidades=8,
                monto=Decimal("2400.50"),
            )
        ],
    ).model_dump(mode="json")
    assert mas["items"][0]["monto"] == 2400.5 and mas["items"][0]["activo"] is False

    repo = ReposicionResponse(
        dias=30,
        cobertura_max_dias=7,
        items=[
            ReposicionItem(
                producto_id="p1",
                sku="A-1",
                nombre="Alimento",
                stock_actual=10,
                stock_minimo=2,
                bajo_minimo=False,
                unidades_vendidas=60,
                venta_diaria=Decimal("2.00"),
                cobertura_dias=5,
                distribuidora_default_id=None,
            )
        ],
    ).model_dump(mode="json")
    assert repo["items"][0]["venta_diaria"] == 2
    assert repo["items"][0]["cobertura_dias"] == 5
    assert repo["items"][0]["distribuidora_default_id"] is None
