"""Normalizacion pura de valores de planilla (C-08, D7)."""

from datetime import date
from decimal import Decimal

import pytest

from app.services.migracion.normalizar import (
    ValorInvalido,
    clave,
    decimal_ar,
    entero,
    margen,
    sku,
    texto,
)

D = Decimal


# --- decimal_ar ---------------------------------------------------------


@pytest.mark.parametrize(
    "crudo, esperado",
    [
        ("$ 18.500,50", D("18500.50")),
        ("18500", D("18500")),
        ("18.5", D("18.5")),
        ("1,5", D("1.5")),
        ("1.234.567,8", D("1234567.8")),
        ("ARS 100", D("100")),
        ("\xa0$\xa01.200,00\xa0", D("1200.00")),
        (18500.0, D("18500")),
        (18500, D("18500")),
        (18.5, D("18.5")),
        ("0.500", D("0.5")),
        ("-12,5", D("-12.5")),
    ],
)
def test_decimal_ar_interpreta_formato_argentino(crudo, esperado):
    valor, advertencias = decimal_ar(crudo)
    assert valor == esperado
    assert advertencias == []


@pytest.mark.parametrize("crudo", ["1.500", "18.500"])
def test_decimal_ar_un_punto_con_tres_decimales_es_miles_con_advertencia(crudo):
    valor, advertencias = decimal_ar(crudo)
    assert valor == D(crudo.replace(".", ""))
    assert len(advertencias) == 1
    assert "miles" in advertencias[0]


@pytest.mark.parametrize("crudo", [None, "", "   ", "\xa0"])
def test_decimal_ar_vacio_es_none(crudo):
    assert decimal_ar(crudo) == (None, [])


@pytest.mark.parametrize(
    "crudo",
    ["abc", "12abc", True, False, date(2026, 1, 2), float("nan"), "1,2,3", "1.2.3,4", "--5"],
)
def test_decimal_ar_invalido_levanta_error_en_castellano(crudo):
    with pytest.raises(ValorInvalido) as exc:
        decimal_ar(crudo)
    assert str(exc.value)


# --- entero ---------------------------------------------------------------


@pytest.mark.parametrize(
    "crudo, esperado", [("20", 20), (20.0, 20), ("20,0", 20), (20, 20), ("0", 0)]
)
def test_entero_acepta_enteros_de_excel(crudo, esperado):
    valor, advertencias = entero(crudo)
    assert valor == esperado
    assert isinstance(valor, int)
    assert advertencias == []


def test_entero_vacio_es_none():
    assert entero("") == (None, [])
    assert entero(None) == (None, [])


def test_entero_con_decimales_es_error():
    with pytest.raises(ValorInvalido, match="decimales"):
        entero("2,5")
    with pytest.raises(ValorInvalido, match="decimales"):
        entero(2.5)


def test_entero_negativo_es_error():
    with pytest.raises(ValorInvalido, match="negativ"):
        entero("-1")


# --- margen ---------------------------------------------------------------


@pytest.mark.parametrize(
    "crudo, esperado",
    [("35", D("0.35")), ("35%", D("0.35")), (35, D("0.35")), ("35,5", D("0.355"))],
)
def test_margen_se_lee_en_puntos_porcentuales(crudo, esperado):
    valor, advertencias = margen(crudo)
    assert valor == esperado
    assert advertencias == []


def test_margen_celda_con_formato_porcentaje_ya_es_fraccion():
    assert margen(0.35, es_porcentaje=True) == (D("0.35"), [])
    assert margen(D("0.355"), es_porcentaje=True) == (D("0.355"), [])


def test_margen_bajo_sin_formato_porcentaje_advierte_si_quiso_decir_otro():
    valor, advertencias = margen("0,35")
    assert valor == D("0.0035")
    assert len(advertencias) == 1
    assert "quisiste decir 35%" in advertencias[0]


def test_margen_cero_explicito_no_advierte():
    assert margen("0") == (D("0"), [])


def test_margen_fuera_de_rango_es_error():
    with pytest.raises(ValorInvalido, match="margen"):
        margen("1000")
    with pytest.raises(ValorInvalido, match="negativ"):
        margen("-5")


def test_margen_vacio_es_none():
    assert margen("") == (None, [])
    assert margen(None) == (None, [])


# --- sku ------------------------------------------------------------------


def test_sku_recorta_y_pasa_a_mayusculas_sin_advertir():
    assert sku(" bal-adu-15 ") == ("BAL-ADU-15", [])


def test_sku_espacios_internos_pasan_a_guion_con_advertencia():
    valor, advertencias = sku("BAL ADU  15")
    assert valor == "BAL-ADU-15"
    assert len(advertencias) == 1


@pytest.mark.parametrize("crudo", [7790001234567, 7790001234567.0, "7790001234567"])
def test_sku_numerico_de_excel_sin_decimales_ni_notacion_cientifica(crudo):
    assert sku(crudo) == ("7790001234567", [])


@pytest.mark.parametrize("crudo", [None, "", "   "])
def test_sku_vacio_es_error(crudo):
    with pytest.raises(ValorInvalido, match="SKU"):
        sku(crudo)


@pytest.mark.parametrize("crudo", [True, 12.5, date(2026, 1, 2)])
def test_sku_de_tipo_invalido_es_error(crudo):
    with pytest.raises(ValorInvalido):
        sku(crudo)


# --- texto / clave --------------------------------------------------------


def test_texto_colapsa_espacios_y_vacio_es_none():
    assert texto("  Balanceado   adulto \xa0 15kg ") == "Balanceado adulto 15kg"
    assert texto("   ") is None
    assert texto(None) is None


def test_texto_numerico_se_convierte_sin_sufijo():
    assert texto(15) == "15"
    assert texto(15.0) == "15"
    assert texto(15.5) == "15.5"


def test_clave_ignora_mayusculas_espacios_y_acentos():
    assert clave("Distribuidora  SUR") == clave("distribuidora sur")
    assert clave("Accesorios Ñandú") == "accesorios nandu"


def test_margen_se_cuantiza_a_diezmilesimas():
    assert margen("33,3333333")[0] == D("0.3333")
    assert margen("33,33335")[0] == D("0.3333")
    assert margen("0,0005")[0] == D("0.0000")
