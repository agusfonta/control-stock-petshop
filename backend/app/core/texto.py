"""Utilidades puras de texto para clientes (C-09, D4/D6).

Las usan los schemas (normalizacion en el borde) y la busqueda
(`GET /api/clientes/buscar`), asi Python y SQL pliegan igual.
"""

import re
import unicodedata

# Pares (caracter acentuado, base) que cubren el castellano. La busqueda SQL
# los aplica con `replace()` anidados porque SQLite solo baja ASCII en
# `lower()`: por eso se listan tambien las mayusculas acentuadas (D6).
PARES_PLEGADO: tuple[tuple[str, str], ...] = (
    ("á", "a"),
    ("é", "e"),
    ("í", "i"),
    ("ó", "o"),
    ("ú", "u"),
    ("ü", "u"),
    ("ñ", "n"),
    ("Á", "A"),
    ("É", "E"),
    ("Í", "I"),
    ("Ó", "O"),
    ("Ú", "U"),
    ("Ü", "U"),
    ("Ñ", "N"),
)

_SEPARADORES_TELEFONO = re.compile(r"[\s\-.()]")
_TELEFONO_VALIDO = re.compile(r"^\+?[0-9]{6,20}$")


def sin_acentos(texto: str) -> str:
    """Minusculas sin acentos y con espacios colapsados (`ñ` -> `n`)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    base = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(base.lower().split())


def solo_digitos(texto: str) -> str:
    """Deja unicamente los digitos ASCII de `texto`."""
    return "".join(c for c in texto if c in "0123456789")


def normalizar_telefono(texto: str) -> str:
    """Quita separadores, conserva un `+` inicial y exige 6 a 20 digitos.

    Levanta ValueError si el resultado no es un telefono valido.
    """
    limpio = _SEPARADORES_TELEFONO.sub("", texto)
    if not _TELEFONO_VALIDO.match(limpio):
        raise ValueError("telefono invalido: use entre 6 y 20 digitos")
    return limpio
