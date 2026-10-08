"""Normalizacion pura de valores de planilla (C-08, D7).

Sin base ni I/O. Cada funcion devuelve `(valor, advertencias)` o levanta
`ValorInvalido` con un mensaje en castellano; `texto` y `clave` son totales.
"""

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.core.texto import sin_acentos

# Precision de las columnas: costo Numeric(10,2), margen_pct Numeric(5,4).
CENTAVOS = Decimal("0.01")
DIEZMILESIMOS = Decimal("0.0001")
MARGEN_MAXIMO = Decimal("9.9999")
MARGEN_ADVERTENCIA = Decimal("0.01")

_MILES = re.compile(r"^\d{1,3}(\.\d{3})+$")
_NUMERO = re.compile(r"^\d+(\.\d+)?$")
_ESPACIOS = re.compile(r"\s+")


class ValorInvalido(ValueError):
    """El valor de una celda no se puede interpretar (mensaje para la usuaria)."""


def _vacio(crudo: object) -> bool:
    return crudo is None or (isinstance(crudo, str) and not crudo.strip())


def _rechazar_tipos_no_numericos(crudo: object) -> None:
    if isinstance(crudo, bool):
        raise ValorInvalido("no es un numero valido (es un valor si/no)")
    if isinstance(crudo, (date, datetime)):
        raise ValorInvalido("no es un numero valido (es una fecha)")
    if not isinstance(crudo, (int, float, Decimal, str)):
        raise ValorInvalido("no es un numero valido")


def _decimal_de_texto(crudo: str) -> tuple[Decimal, list[str]]:
    t = re.sub(r"(?i)ars|\$", "", crudo)
    t = _ESPACIOS.sub("", t)
    signo = ""
    if t[:1] in "+-":
        signo, t = t[0], t[1:]
    advertencias: list[str] = []
    if "." in t and "," in t:
        # El ultimo separador es el decimal; el otro agrupa miles.
        if t.rfind(",") < t.rfind("."):
            raise ValorInvalido(f"numero con formato ambiguo: {crudo!r}")
        entera, _, decimales = t.rpartition(",")
        if not _MILES.match(entera):
            raise ValorInvalido(f"numero con formato invalido: {crudo!r}")
        t = entera.replace(".", "") + "." + decimales
    elif "," in t:
        if t.count(",") > 1:
            raise ValorInvalido(f"numero con formato invalido: {crudo!r}")
        t = t.replace(",", ".")
    elif "." in t and _MILES.match(t) and not t.startswith("0"):
        if t.count(".") == 1:
            advertencias.append(
                f"'{crudo.strip()}' se interpreto como miles ({t.replace('.', '')}); "
                "revisar si era un decimal"
            )
        t = t.replace(".", "")
    if not _NUMERO.match(t):
        raise ValorInvalido(f"no es un numero valido: {crudo!r}")
    return Decimal(signo + t), advertencias


def decimal_ar(crudo: object) -> tuple[Decimal | None, list[str]]:
    """Numero en formato argentino (`$ 18.500,50`) o nativo de Excel."""
    if _vacio(crudo):
        return None, []
    _rechazar_tipos_no_numericos(crudo)
    if isinstance(crudo, Decimal):
        return crudo, []
    if isinstance(crudo, (int, float)):
        try:
            valor = Decimal(str(crudo))
        except InvalidOperation:
            raise ValorInvalido("no es un numero valido") from None
        if not valor.is_finite():
            raise ValorInvalido("no es un numero valido")
        return valor, []
    return _decimal_de_texto(str(crudo))


def entero(crudo: object) -> tuple[int | None, list[str]]:
    """Unidades enteras >= 0 (`20`, `20.0`, `20,0`); decimales son error."""
    valor, advertencias = decimal_ar(crudo)
    if valor is None:
        return None, []
    if valor != valor.to_integral_value():
        raise ValorInvalido("debe ser un numero entero, sin decimales")
    if valor < 0:
        raise ValorInvalido("no puede ser negativo")
    return int(valor), advertencias


def margen(
    crudo: object, es_porcentaje: bool = False
) -> tuple[Decimal | None, list[str]]:
    """Margen como fraccion (0.35). La planilla lo expresa en puntos (35)."""
    if isinstance(crudo, str):
        crudo = crudo.replace("%", "")
    valor, advertencias = decimal_ar(crudo)
    if valor is None:
        return None, []
    ya_es_fraccion = es_porcentaje and not isinstance(crudo, str)
    fraccion = valor if ya_es_fraccion else valor / 100
    fraccion = fraccion.quantize(DIEZMILESIMOS, rounding=ROUND_HALF_UP)
    if fraccion < 0:
        raise ValorInvalido("el margen no puede ser negativo")
    if fraccion > MARGEN_MAXIMO:
        raise ValorInvalido("el margen supera el maximo admitido (999,99%)")
    if 0 < fraccion < MARGEN_ADVERTENCIA:
        sugerencia = "" if ya_es_fraccion else f"; ¿quisiste decir {valor * 100:.0f}%?"
        advertencias.append(f"margen menor a 1% ({fraccion * 100:.2f}%){sugerencia}")
    return fraccion, advertencias


def sku(crudo: object) -> tuple[str, list[str]]:
    """SKU en mayusculas; espacios internos pasan a `-` (con advertencia)."""
    if isinstance(crudo, bool) or isinstance(crudo, (date, datetime)):
        raise ValorInvalido("el SKU no es valido")
    if isinstance(crudo, float):
        if not crudo.is_integer():
            raise ValorInvalido("el SKU no es valido (tiene decimales)")
        crudo = int(crudo)
    if isinstance(crudo, int):
        return str(crudo), []
    if _vacio(crudo):
        raise ValorInvalido("falta el SKU")
    if not isinstance(crudo, str):
        raise ValorInvalido("el SKU no es valido")
    limpio = crudo.strip().upper()
    con_guiones = _ESPACIOS.sub("-", limpio)
    if con_guiones != limpio:
        return con_guiones, [f"los espacios del SKU se reemplazaron por '-': {con_guiones}"]
    return limpio, []


def texto(crudo: object) -> str | None:
    """Texto recortado y con espacios colapsados; vacio es None."""
    if crudo is None:
        return None
    if isinstance(crudo, float) and crudo.is_integer():
        crudo = int(crudo)
    limpio = _ESPACIOS.sub(" ", str(crudo)).strip()
    return limpio or None


def clave(crudo: object) -> str:
    """Clave de comparacion: minusculas, sin acentos, espacios colapsados."""
    return sin_acentos(str(crudo)) if crudo is not None else ""
