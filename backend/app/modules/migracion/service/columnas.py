"""Mapeo tolerante de encabezados de planilla a campos canonicos (C-08, D2)."""

import re
from dataclasses import dataclass, field

from app.core.texto import sin_acentos

CAMPOS: tuple[str, ...] = (
    "sku",
    "nombre",
    "categoria",
    "marca",
    "distribuidora",
    "costo",
    "margen_pct",
    "precio_venta",
    "stock_inicial",
    "stock_minimo",
    "unidad",
)
OBLIGATORIOS: tuple[str, ...] = ("sku", "nombre", "costo")

_PUNTUACION = re.compile(r"[_\-.%]+")


def clave_columna(encabezado: object) -> str:
    """Clave de comparacion: sin acentos/mayusculas, `_ - . %` como espacio."""
    return " ".join(_PUNTUACION.sub(" ", sin_acentos(str(encabezado))).split())


_ALIAS_CRUDOS: dict[str, tuple[str, ...]] = {
    "sku": ("sku", "codigo", "cod", "codigo producto", "cod producto",
            "codigo articulo", "codigo de barras", "ean"),
    "nombre": ("nombre", "descripcion", "producto", "detalle", "articulo",
               "nombre producto", "denominacion"),
    "categoria": ("categoria", "rubro", "familia"),
    "marca": ("marca",),
    "distribuidora": ("distribuidora", "proveedor", "distribuidor",
                      "proveedor habitual"),
    "costo": ("costo", "precio costo", "precio de costo", "costo unitario",
              "valor costo", "precio compra", "precio de compra"),
    "margen_pct": ("margen", "margen pct", "margen porcentaje", "ganancia",
                   "ganancia pct", "margen de ganancia", "utilidad", "markup"),
    "precio_venta": ("precio venta", "precio de venta", "pvp", "precio publico",
                     "precio al publico", "precio"),
    "stock_inicial": ("stock", "stock inicial", "stock actual", "existencia",
                      "existencias", "cantidad"),
    "stock_minimo": ("stock minimo", "stock min", "minimo", "punto de pedido"),
    "unidad": ("unidad", "unidad de medida", "um"),
}
ALIAS: dict[str, frozenset[str]] = {
    campo: frozenset(clave_columna(a) for a in alias)
    for campo, alias in _ALIAS_CRUDOS.items()
}


@dataclass(frozen=True)
class ResultadoColumnas:
    """Indice campo->posicion (0-based), columnas ignoradas y errores globales."""

    indices: dict[str, int] = field(default_factory=dict)
    ignoradas: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def _posiciones_explicitas(
    claves: list[str], encabezados: list[object], mapeo: dict[str, str], errores: list[str]
) -> dict[int, str]:
    """Posicion -> campo para los pares del mapeo explicito (los valida)."""
    explicitas: dict[int, str] = {}
    for campo, encabezado in mapeo.items():
        if campo not in CAMPOS:
            errores.append(f"el mapeo nombra un campo desconocido: {campo}")
            continue
        posiciones = [i for i, c in enumerate(claves) if c == clave_columna(encabezado)]
        if not posiciones:
            errores.append(
                f"el mapeo de {campo} apunta a un encabezado inexistente: {encabezado}"
            )
        elif len(posiciones) > 1:
            errores.append(f"el encabezado '{encabezado}' del mapeo aparece mas de una vez")
        else:
            explicitas[posiciones[0]] = campo
    return explicitas


def resolver_columnas(
    encabezados: list[object], mapeo: dict[str, str] | None
) -> ResultadoColumnas:
    """Resuelve que columna aporta cada campo (mapeo explicito > alias)."""
    errores: list[str] = []
    claves = [clave_columna(h) if h is not None else "" for h in encabezados]
    explicitas = _posiciones_explicitas(claves, encabezados, mapeo or {}, errores)
    campos_explicitos = set(explicitas.values())

    candidatas: dict[str, list[int]] = {c: [] for c in CAMPOS}
    for pos, campo in explicitas.items():
        candidatas[campo].append(pos)
    for pos, clave in enumerate(claves):
        if not clave or pos in explicitas:
            continue
        for campo in CAMPOS:
            if campo not in campos_explicitos and clave in ALIAS[campo]:
                candidatas[campo].append(pos)
                break

    indices: dict[str, int] = {}
    usadas: set[int] = set()
    for campo, posiciones in candidatas.items():
        if len(posiciones) > 1:
            nombres = " y ".join(f"'{encabezados[p]}'" for p in posiciones)
            errores.append(f"mas de una columna para {campo}: {nombres}")
        if posiciones:
            indices[campo] = posiciones[0]
            usadas.update(posiciones)
    errores.extend(
        f"falta columna obligatoria: {c}" for c in OBLIGATORIOS if c not in indices
    )
    ignoradas = [
        str(h).strip()
        for pos, h in enumerate(encabezados)
        if claves[pos] and pos not in usadas
    ]
    return ResultadoColumnas(indices, ignoradas, errores)
