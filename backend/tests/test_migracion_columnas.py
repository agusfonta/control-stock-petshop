"""Mapeo tolerante de columnas de la planilla (C-08, D2)."""

import csv
from pathlib import Path

import pytest

from app.services.migracion.columnas import OBLIGATORIOS, resolver_columnas

PLANTILLA = Path(__file__).resolve().parents[2] / "data" / "plantilla_productos.csv"
BASE = ["SKU", "Nombre", "Costo"]


@pytest.mark.parametrize(
    "encabezado, campo",
    [
        ("Código", "sku"),
        ("Descripción", "nombre"),
        ("Producto", "nombre"),
        ("Proveedor", "distribuidora"),
        ("Precio Costo", "costo"),
        ("precio_costo", "costo"),
        ("Ganancia %", "margen_pct"),
        ("margen_pct", "margen_pct"),
        ("PVP", "precio_venta"),
        ("Precio venta", "precio_venta"),
        ("Stock", "stock_inicial"),
        ("stock_actual", "stock_inicial"),
        ("Stock inicial", "stock_inicial"),
        ("Stock mínimo", "stock_minimo"),
        ("Rubro", "categoria"),
        ("  MARCA ", "marca"),
        ("Unidad", "unidad"),
    ],
)
def test_alias_se_reconocen_sin_acentos_ni_mayusculas(encabezado, campo):
    # Los indices se informan aunque falten obligatorias (los errores van aparte).
    assert resolver_columnas([encabezado], None).indices == {campo: 0}


def test_la_plantilla_del_proyecto_mapea_completa():
    with PLANTILLA.open(encoding="utf-8", newline="") as f:
        encabezados = next(csv.reader(f))
    r = resolver_columnas(encabezados, None)
    assert r.errores == []
    assert r.ignoradas == []
    assert set(r.indices) == {
        "sku", "nombre", "categoria", "costo", "margen_pct",
        "stock_inicial", "stock_minimo", "distribuidora",
    }
    assert r.indices["stock_inicial"] == encabezados.index("stock_actual")


def test_mapeo_explicito_gana_sobre_los_alias():
    r = resolver_columnas(["SKU", "Nombre", "Precio Costo", "Valor compra"],
                          {"costo": "Valor compra"})
    assert r.errores == []
    assert r.indices["costo"] == 3
    assert "Precio Costo" in r.ignoradas


def test_mapeo_explicito_resuelve_encabezado_no_reconocido():
    r = resolver_columnas(["SKU", "Nombre", "Valor compra"], {"costo": "valor  COMPRA"})
    assert r.errores == []
    assert r.indices["costo"] == 2


def test_falta_columna_obligatoria_es_error_global():
    r = resolver_columnas(["SKU", "Nombre", "Observaciones"], None)
    assert r.errores == ["falta columna obligatoria: costo"]


def test_falta_mas_de_una_obligatoria_lista_todas():
    r = resolver_columnas(["Marca"], None)
    assert [e for e in r.errores if e.startswith("falta columna")] == [
        f"falta columna obligatoria: {c}" for c in OBLIGATORIOS
    ]


def test_dos_encabezados_al_mismo_campo_es_error_global():
    r = resolver_columnas([*BASE, "Precio costo"], None)
    assert len(r.errores) == 1
    assert "costo" in r.errores[0] and "Precio costo" in r.errores[0]


def test_mapeo_explicito_a_encabezado_inexistente_es_error_global():
    r = resolver_columnas(BASE, {"marca": "Fabricante"})
    assert any("Fabricante" in e for e in r.errores)


def test_mapeo_a_campo_desconocido_es_error_global():
    r = resolver_columnas(BASE, {"color": "SKU"})
    assert any("color" in e for e in r.errores)


def test_columna_desconocida_se_lista_como_ignorada_sin_bloquear():
    r = resolver_columnas([*BASE, "Observaciones", None], None)
    assert r.errores == []
    assert r.ignoradas == ["Observaciones"]
