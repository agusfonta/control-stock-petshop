"""Utilidades de texto puras para clientes (C-09 tasks 1.2/1.3, RED-first)."""

import pytest

from app.core.texto import normalizar_telefono, sin_acentos, solo_digitos

# --- sin_acentos ---


def test_sin_acentos_quita_tildes_y_baja_a_minusculas() -> None:
    assert sin_acentos("José Núñez") == "jose nunez"


def test_sin_acentos_cubre_todas_las_mayusculas_acentuadas() -> None:
    assert sin_acentos("ÁÉÍÓÚÜÑ") == "aeiouun"


def test_sin_acentos_colapsa_espacios_y_recorta() -> None:
    assert sin_acentos("  Ana   María \t Pérez  ") == "ana maria perez"


def test_sin_acentos_texto_ascii_solo_baja_a_minusculas() -> None:
    assert sin_acentos("ANA@Mail.com") == "ana@mail.com"


# --- solo_digitos ---


def test_solo_digitos_quita_separadores() -> None:
    assert solo_digitos("5555-12") == "555512"


def test_solo_digitos_sin_digitos_devuelve_vacio() -> None:
    assert solo_digitos("ana") == ""


# --- normalizar_telefono ---


def test_normalizar_telefono_quita_espacios_y_guiones() -> None:
    assert normalizar_telefono("11 5555-1234") == "1155551234"


def test_normalizar_telefono_conserva_mas_inicial() -> None:
    assert normalizar_telefono("+54 (11) 5555.1234") == "+541155551234"


@pytest.mark.parametrize("invalido", ["abc", "12345", "1" * 21, "11+5555-1234", "١٢٣٤٥٦٧"])
def test_normalizar_telefono_invalido_levanta_error(invalido: str) -> None:
    with pytest.raises(ValueError):
        normalizar_telefono(invalido)


def test_normalizar_telefono_limites_6_y_20_digitos_validos() -> None:
    assert normalizar_telefono("123456") == "123456"
    assert normalizar_telefono("1" * 20) == "1" * 20
