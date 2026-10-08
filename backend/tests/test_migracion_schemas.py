"""Schemas estrictos del reporte de importacion (C-08, D2/D11)."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    ColumnasReporte,
    FilaReporte,
    MapeoColumnas,
    MotivoReporte,
    ReporteImportacion,
    TotalesImportacion,
)


def _fila(**kw):
    base = {"fila": 2, "sku": "A-1", "estado": "ok", "accion": "crear"}
    return FilaReporte(**{**base, **kw})


def _totales(**kw):
    base = dict(
        filas=0, ok=0, advertencias=0, errores=0, crear=0, actualizar=0,
        sin_cambios=0, distribuidoras_a_crear=0, unidades_apertura=0,
    )
    return TotalesImportacion(**{**base, **kw})


def _reporte(**kw):
    base = dict(
        archivo="p.xlsx", confirmado=False, lote_id=None, errores_globales=[],
        columnas=ColumnasReporte(mapeadas={"sku": "SKU"}, ignoradas=[]),
        totales=_totales(), distribuidoras_a_crear=[], filas=[],
    )
    return ReporteImportacion(**{**base, **kw})


# --- MapeoColumnas ---------------------------------------------------------


def test_mapeo_acepta_campo_conocido_y_lo_expone_como_dict():
    m = MapeoColumnas.model_validate({"costo": "Valor compra"})
    assert m.a_dict() == {"costo": "Valor compra"}
    assert MapeoColumnas.model_validate({}).a_dict() == {}


def test_mapeo_rechaza_campo_desconocido():
    with pytest.raises(ValidationError):
        MapeoColumnas.model_validate({"color": "Color"})


@pytest.mark.parametrize("vacio", ["", "   "])
def test_mapeo_rechaza_encabezado_vacio(vacio):
    with pytest.raises(ValidationError):
        MapeoColumnas.model_validate({"costo": vacio})


def test_mapeo_rechaza_valor_que_no_es_texto():
    with pytest.raises(ValidationError):
        MapeoColumnas.model_validate({"costo": 3})


# --- FilaReporte -----------------------------------------------------------


def test_fila_exige_numero_desde_2():
    with pytest.raises(ValidationError):
        _fila(fila=1)


def test_fila_rechaza_estado_y_accion_desconocidos():
    with pytest.raises(ValidationError):
        _fila(estado="raro")
    with pytest.raises(ValidationError):
        _fila(accion="borrar")


def test_fila_error_no_tiene_accion_y_exige_un_motivo_de_error():
    motivo = MotivoReporte(campo="costo", mensaje="debe ser mayor a 0", gravedad="error")
    fila = _fila(estado="error", accion=None, sku=None, motivos=[motivo])
    assert fila.accion is None
    with pytest.raises(ValidationError):
        _fila(estado="error", accion="crear", motivos=[motivo])
    with pytest.raises(ValidationError):
        _fila(estado="error", accion=None, motivos=[])


def test_fila_no_error_exige_accion():
    with pytest.raises(ValidationError):
        _fila(estado="ok", accion=None)


def test_fila_estado_debe_coincidir_con_la_gravedad_de_los_motivos():
    adv = MotivoReporte(campo=None, mensaje="revisar", gravedad="advertencia")
    assert _fila(estado="advertencia", motivos=[adv]).estado == "advertencia"
    with pytest.raises(ValidationError):
        _fila(estado="ok", motivos=[adv])
    with pytest.raises(ValidationError):
        _fila(estado="advertencia", motivos=[])


def test_fila_campos_cambiados_solo_al_actualizar():
    assert _fila(accion="actualizar", campos_cambiados=["costo"]).campos_cambiados == ["costo"]
    with pytest.raises(ValidationError):
        _fila(accion="crear", campos_cambiados=["costo"])


def test_motivo_exige_mensaje():
    with pytest.raises(ValidationError):
        MotivoReporte(campo="costo", mensaje="", gravedad="error")


# --- Totales / ReporteImportacion -------------------------------------------


def test_totales_coherentes_o_error():
    assert _totales(filas=3, ok=1, advertencias=1, errores=1, crear=2).filas == 3
    with pytest.raises(ValidationError):
        _totales(filas=3, ok=1, advertencias=1, errores=0)
    with pytest.raises(ValidationError):
        _totales(filas=3, ok=3, crear=1, actualizar=1)  # acciones != filas sin error


def test_reporte_prohibe_campos_extra():
    with pytest.raises(ValidationError):
        ReporteImportacion.model_validate(
            {**_reporte().model_dump(), "sorpresa": 1}
        )


def test_reporte_lote_id_solo_si_confirmado():
    assert _reporte(confirmado=True, lote_id="abc").lote_id == "abc"
    with pytest.raises(ValidationError):
        _reporte(confirmado=False, lote_id="abc")
    with pytest.raises(ValidationError):
        _reporte(confirmado=True, lote_id=None)


def test_reporte_totales_deben_coincidir_con_las_filas():
    f1 = _fila(fila=2)
    f2 = _fila(fila=3, sku="A-2")
    ok = _reporte(filas=[f1, f2], totales=_totales(filas=2, ok=2, crear=2))
    assert len(ok.filas) == 2
    with pytest.raises(ValidationError):
        _reporte(filas=[f1, f2], totales=_totales(filas=1, ok=1, crear=1))
    with pytest.raises(ValidationError):
        _reporte(filas=[f1, f2], totales=_totales(filas=2, ok=2, sin_cambios=2))


def test_reporte_distribuidoras_a_crear_coincide_con_el_total():
    r = _reporte(distribuidoras_a_crear=["Sur"], totales=_totales(distribuidoras_a_crear=1))
    assert r.distribuidoras_a_crear == ["Sur"]
    with pytest.raises(ValidationError):
        _reporte(distribuidoras_a_crear=["Sur"], totales=_totales())


def test_reporte_confirmado_no_admite_errores():
    err = MotivoReporte(campo="costo", mensaje="mal", gravedad="error")
    fila = _fila(estado="error", accion=None, motivos=[err])
    totales = _totales(filas=1, errores=1)
    with pytest.raises(ValidationError):
        _reporte(confirmado=True, lote_id="x", filas=[fila], totales=totales)
    with pytest.raises(ValidationError):
        _reporte(confirmado=True, lote_id="x", errores_globales=["falta columna"])
