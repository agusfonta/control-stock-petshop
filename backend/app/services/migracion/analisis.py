"""Analisis / dry-run de la planilla contra la base (C-08, D3/D5/D7/D8/D9).

Nunca escribe ni toma locks: lee una foto de la base y decide, fila por fila,
la accion prevista y los motivos. `aplicar.py` ejecuta el `Plan` resultante.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Distribuidora, Producto
from app.schemas import ProductoCreate, TotalesImportacion
from app.services.migracion.columnas import ResultadoColumnas
from app.services.migracion.lectura import Celda, FilaCruda, Planilla
from app.services.migracion.normalizar import (
    CENTAVOS,
    DIEZMILESIMOS,
    MARGEN_MAXIMO,
    ValorInvalido,
    clave,
    decimal_ar,
    entero,
    margen,
    sku,
    texto,
)

COSTO_MAXIMO = Decimal("99999999.99")  # Numeric(10, 2)
UNIDADES = {"unidad": "unidad", "bolsa": "bolsa", "caja": "caja"}
TOLERANCIA_PRECIO = Decimal("0.01")
MSG_FORMULA = (
    "la celda es una formula sin valor guardado: abri el archivo en Excel "
    "y guardalo de nuevo"
)


@dataclass(frozen=True)
class MotivoPlan:
    campo: str | None
    mensaje: str
    gravedad: str  # "error" | "advertencia"


@dataclass(frozen=True)
class FilaPlan:
    fila: int
    sku: str | None
    estado: str
    accion: str | None
    motivos: tuple[MotivoPlan, ...]
    campos_cambiados: tuple[str, ...] = ()
    valores: dict = field(default_factory=dict)
    producto_id: str | None = None


@dataclass(frozen=True)
class Plan:
    filas: tuple[FilaPlan, ...] = ()
    errores_globales: tuple[str, ...] = ()
    distribuidoras_a_crear: tuple[str, ...] = ()

    @property
    def hay_errores(self) -> bool:
        return bool(self.errores_globales) or any(f.estado == "error" for f in self.filas)

    @property
    def totales(self) -> TotalesImportacion:
        contar = lambda attr, v: sum(getattr(f, attr) == v for f in self.filas)  # noqa: E731
        apertura = sum(
            f.valores.get("stock_inicial") or 0
            for f in self.filas
            if f.accion == "crear"
        )
        return TotalesImportacion(
            filas=len(self.filas),
            ok=contar("estado", "ok"),
            advertencias=contar("estado", "advertencia"),
            errores=contar("estado", "error"),
            crear=contar("accion", "crear"),
            actualizar=contar("accion", "actualizar"),
            sin_cambios=contar("accion", "sin_cambios"),
            distribuidoras_a_crear=len(self.distribuidoras_a_crear),
            unidades_apertura=apertura,
        )


class _Acumulador:
    """Motivos de una fila en construccion."""

    def __init__(self) -> None:
        self.motivos: list[MotivoPlan] = []

    def error(self, campo: str | None, mensaje: str) -> None:
        self.motivos.append(MotivoPlan(campo, mensaje, "error"))

    def aviso(self, campo: str | None, mensaje: str) -> None:
        self.motivos.append(MotivoPlan(campo, mensaje, "advertencia"))

    @property
    def hay_error(self) -> bool:
        return any(m.gravedad == "error" for m in self.motivos)


Normalizador = Callable[[Celda], tuple[object, list[str]]]


def _leer(
    acc: _Acumulador, fila: FilaCruda, indices: dict[str, int], campo: str, fn: Normalizador
) -> tuple[object, bool]:
    """Normaliza la celda de `campo`: `(valor|None, fallo)`; registra los motivos."""
    pos = indices.get(campo)
    if pos is None:
        return None, False
    celda = fila.celdas[pos]
    if celda.formula_sin_valor:
        acc.error(campo, MSG_FORMULA)
        return None, True
    try:
        valor, avisos = fn(celda)
    except ValorInvalido as exc:
        acc.error(campo, str(exc))
        return None, True
    for aviso in avisos:
        acc.aviso(campo, aviso)
    return valor, False


def _traducir(err: dict) -> str:
    """Mensaje en castellano para un error de Pydantic (por `type`)."""
    tipo = err["type"]
    ctx = err.get("ctx") or {}
    if tipo == "string_pattern_mismatch":
        return "formato invalido: use solo letras, numeros, '-' y '_' (sin espacios ni barras)"
    if tipo == "string_too_short":
        return "no puede estar vacio"
    if tipo == "string_too_long":
        return f"supera el maximo de {ctx.get('max_length')} caracteres"
    if tipo == "greater_than":
        return f"debe ser mayor a {ctx.get('gt')}"
    if tipo == "greater_than_equal":
        return "no puede ser negativo"
    return str(err["msg"])


def _validar(acc: _Acumulador, datos: dict, fallidos: set[str]) -> None:
    """Reglas de alta de producto: reutiliza ProductoCreate (D8)."""
    try:
        ProductoCreate.model_validate(datos)
    except ValidationError as exc:
        for err in exc.errors():
            campo = str(err["loc"][0]) if err["loc"] else None
            if campo not in fallidos:
                acc.error(campo, _traducir(err))


def _cuantizar(valor: Decimal, paso: Decimal) -> Decimal:
    return valor.quantize(paso, rounding=ROUND_HALF_UP)


def _costo(c: Celda) -> tuple[Decimal | None, list[str]]:
    valor, avisos = decimal_ar(c.valor)
    if valor is None:
        return None, avisos
    valor = _cuantizar(valor, CENTAVOS)
    if valor > COSTO_MAXIMO:
        raise ValorInvalido("supera el maximo admitido (99.999.999,99)")
    return valor, avisos


def _precio(c: Celda) -> tuple[Decimal | None, list[str]]:
    valor, avisos = _costo(c)
    if valor is not None and valor <= 0:
        raise ValorInvalido("el precio de venta debe ser mayor a 0")
    return valor, avisos


def _unidad(c: Celda) -> tuple[str | None, list[str]]:
    crudo = texto(c.valor)
    if crudo is None:
        return None, []
    if clave(crudo) not in UNIDADES:
        raise ValorInvalido(f"unidad no admitida: {crudo} (use unidad, bolsa o caja)")
    return UNIDADES[clave(crudo)], []


@dataclass(frozen=True)
class _Existente:
    """Producto de la base, tal como esta (foto de solo lectura)."""

    id: str
    sku: str
    nombre: str
    marca: str | None
    categoria: str | None
    unidad: str
    costo: Decimal
    margen_pct: Decimal
    stock_actual: int
    stock_minimo: int
    distribuidora_id: str | None
    activo: bool


@dataclass(frozen=True)
class _DistribuidoraExistente:
    id: str
    activo: bool


@dataclass
class _Contexto:
    """Foto de la base + grafias nuevas vistas en el archivo (D3, D9)."""

    productos: dict[str, list[_Existente]]
    distribuidoras: dict[str, list[_DistribuidoraExistente]]
    categorias: dict[str, str]  # clave -> grafia a usar
    distribuidoras_nuevas: dict[str, str] = field(default_factory=dict)


def _foto(db: Session) -> _Contexto:
    productos: dict[str, list[_Existente]] = {}
    for p in db.execute(select(Producto)).scalars():
        productos.setdefault(p.sku.upper(), []).append(
            _Existente(
                p.id, p.sku, p.nombre, p.marca, p.categoria, p.unidad,
                Decimal(str(p.costo)), Decimal(str(p.margen_pct)),
                p.stock_actual, p.stock_minimo, p.distribuidora_default_id, p.activo,
            )
        )
    distribuidoras: dict[str, list[_DistribuidoraExistente]] = {}
    for d in db.execute(select(Distribuidora)).scalars():
        distribuidoras.setdefault(clave(d.nombre), []).append(
            _DistribuidoraExistente(d.id, d.activo)
        )
    usos = db.execute(
        select(Producto.categoria, func.count())
        .where(Producto.categoria.is_not(None))
        .group_by(Producto.categoria)
    ).all()
    categorias: dict[str, str] = {}
    for nombre, _ in sorted(usos, key=lambda u: (-u[1], u[0])):
        categorias.setdefault(clave(nombre), nombre)
    return _Contexto(productos, distribuidoras, categorias)


def _resolver_margen(
    acc: _Acumulador,
    fila: FilaCruda,
    indices: dict[str, int],
    costo: Decimal | None,
    nuevo: bool,
) -> tuple[Decimal | None, bool]:
    """Margen de la fila: `(valor|None, fallo)`.

    Explicito, derivado del precio de venta (D7) o, sin ningun dato, 0 con
    advertencia en productos nuevos (en existentes queda `None` = sin cambio).
    """
    m, fallo_m = _leer(acc, fila, indices, "margen_pct", lambda c: margen(c.valor, c.es_porcentaje))
    p, fallo_p = _leer(acc, fila, indices, "precio_venta", _precio)
    if fallo_m or fallo_p:
        return None, True
    if m is not None:
        if p is not None and costo:
            esperado = costo * (1 + m)
            if abs(p - esperado) / esperado > TOLERANCIA_PRECIO:
                acc.aviso(
                    "precio_venta",
                    f"el precio de la planilla ({p}) difiere del calculado "
                    f"({_cuantizar(esperado, CENTAVOS)}); se usa el margen",
                )
        return m, False
    if p is None:
        if nuevo:
            acc.aviso("margen_pct", "sin margen ni precio de venta: se usa margen 0")
            return Decimal("0"), False
        return None, False
    if not costo:
        return None, True  # sin costo valido no se puede derivar; el costo ya es error
    derivado = _cuantizar(p / costo - 1, DIEZMILESIMOS)
    if derivado < 0:
        acc.error("precio_venta", f"el precio de venta ({p}) es menor al costo ({costo})")
        return None, True
    if derivado > MARGEN_MAXIMO:
        acc.error("precio_venta", "el precio de venta es demasiado alto respecto del costo")
        return None, True
    acc.aviso(
        "margen_pct",
        f"margen derivado del precio de venta: {derivado * 100:.2f}% (puede diferir en centavos)",
    )
    return derivado, False


def _skus_repetidos(filas: tuple[FilaCruda, ...], indices: dict[str, int]) -> dict[str, list[int]]:
    """SKU normalizado -> numeros de fila, solo para los que aparecen mas de una vez."""
    vistos: dict[str, list[int]] = {}
    for f in filas:
        try:
            valor, _ = sku(f.celdas[indices["sku"]].valor)
        except ValorInvalido:
            continue
        vistos.setdefault(valor, []).append(f.numero)
    return {k: v for k, v in vistos.items() if len(v) > 1}


def _citar(filas: list[int], propia: int) -> str:
    otras = [str(n) for n in filas if n != propia]
    if len(otras) == 1:
        return f"el SKU esta repetido en la fila {otras[0]}"
    return f"el SKU esta repetido en las filas {', '.join(otras[:-1])} y {otras[-1]}"


def _buscar_existente(acc: _Acumulador, ctx: _Contexto, codigo: str) -> tuple[_Existente | None, bool]:
    """`(existente|None, bloqueado)`: SKU ambiguo o de un producto dado de baja."""
    candidatos = ctx.productos.get(codigo.upper(), [])
    if len(candidatos) > 1:
        grafias = " y ".join(f"'{c.sku}'" for c in candidatos)
        acc.error("sku", f"hay mas de un producto con ese SKU ({grafias}); unificalos antes de importar")
        return None, True
    if candidatos and not candidatos[0].activo:
        acc.error("sku", "el producto esta dado de baja; reactivalo antes de importar")
        return None, True
    return (candidatos[0] if candidatos else None), False


def _resolver_distribuidora(
    acc: _Acumulador, ctx: _Contexto, nombre: str
) -> tuple[str | None, str | None, bool]:
    """`(id existente, nombre a crear, fallo)` segun D9."""
    k = clave(nombre)
    coincidencias = ctx.distribuidoras.get(k, [])
    activas = [d for d in coincidencias if d.activo]
    if len(activas) == 1:
        return activas[0].id, None, False
    if len(activas) > 1:
        acc.error("distribuidora", f"hay mas de una distribuidora llamada '{nombre}'")
        return None, None, True
    if coincidencias:
        acc.error("distribuidora", f"la distribuidora '{nombre}' esta dada de baja")
        return None, None, True
    return None, ctx.distribuidoras_nuevas.setdefault(k, nombre), False


CAMPOS_ACTUALIZABLES = ("nombre", "categoria", "marca", "unidad", "costo", "margen_pct", "stock_minimo")
_PASOS = {"costo": CENTAVOS, "margen_pct": DIEZMILESIMOS}


def _distinto(campo: str, nuevo: object, actual: object) -> bool:
    """Comparacion cuantizada para que re-importar no genere falsos cambios."""
    if campo in _PASOS and nuevo is not None and actual is not None:
        return _cuantizar(Decimal(nuevo), _PASOS[campo]) != _cuantizar(Decimal(actual), _PASOS[campo])
    return nuevo != actual


def _plan_fila(
    fila: FilaCruda, codigo: str | None, acc: _Acumulador, accion: str | None,
    valores: dict, cambios: tuple[str, ...] = (), producto_id: str | None = None,
) -> FilaPlan:
    estado = "error" if acc.hay_error else "advertencia" if acc.motivos else "ok"
    return FilaPlan(
        fila=fila.numero, sku=codigo, estado=estado,
        accion=None if estado == "error" else accion,
        motivos=tuple(acc.motivos), campos_cambiados=cambios if estado != "error" else (),
        valores=valores, producto_id=producto_id,
    )


def _analizar_fila(
    fila: FilaCruda, indices: dict[str, int], repetidos: dict[str, list[int]], ctx: _Contexto
) -> FilaPlan:
    acc = _Acumulador()
    fallidos: set[str] = set()

    def leer(campo: str, fn: Normalizador) -> object:
        valor, fallo = _leer(acc, fila, indices, campo, fn)
        if fallo:
            fallidos.add(campo)
        return valor

    solo_texto: Normalizador = lambda c: (texto(c.valor), [])  # noqa: E731
    codigo = leer("sku", lambda c: sku(c.valor))
    if codigo is not None and codigo in repetidos:
        acc.error("sku", _citar(repetidos[codigo], fila.numero))
        fallidos.add("sku")
    existente, bloqueado = (None, False) if codigo is None else _buscar_existente(acc, ctx, codigo)
    if bloqueado:
        return _plan_fila(fila, codigo, acc, None, {})
    nuevo = existente is None
    nombre = leer("nombre", solo_texto)
    if nombre is None and nuevo and "nombre" not in fallidos:
        acc.error("nombre", "falta el nombre")
        fallidos.add("nombre")
    costo = leer("costo", _costo)
    if costo is None and nuevo and "costo" not in fallidos:
        acc.error("costo", "falta el costo")
        fallidos.add("costo")
    costo_efectivo = costo if costo is not None else (None if nuevo else existente.costo)
    m, fallo_margen = _resolver_margen(acc, fila, indices, costo_efectivo, nuevo)
    if fallo_margen:
        fallidos.add("margen_pct")
    categoria = leer("categoria", solo_texto)
    if categoria:
        categoria = ctx.categorias.setdefault(clave(categoria), categoria)
    marca = leer("marca", solo_texto)
    unidad = leer("unidad", _unidad)
    stock_minimo = leer("stock_minimo", lambda c: entero(c.valor))
    stock_inicial = leer("stock_inicial", lambda c: entero(c.valor))
    dist_nombre = leer("distribuidora", solo_texto)
    dist_id = None if nuevo else existente.distribuidora_id
    dist_nueva = None
    if dist_nombre:
        dist_id, dist_nueva, fallo = _resolver_distribuidora(acc, ctx, dist_nombre)
        if fallo:
            fallidos.add("distribuidora")
    return _cerrar_fila(
        fila, acc, fallidos, codigo, existente,
        dict(nombre=nombre, categoria=categoria, marca=marca, unidad=unidad,
             costo=costo, margen_pct=m, stock_minimo=stock_minimo),
        stock_inicial, (dist_id, dist_nueva, bool(dist_nombre)),
    )


_DEFECTOS = {"unidad": "unidad", "margen_pct": Decimal("0"), "stock_minimo": 0}


def _cerrar_fila(
    fila: FilaCruda, acc: _Acumulador, fallidos: set[str], codigo: str | None,
    existente: _Existente | None, leidos: dict, stock_inicial: int | None,
    distribuidora: tuple[str | None, str | None, bool],
) -> FilaPlan:
    """Valores efectivos, validacion con ProductoCreate, accion y cambios."""
    dist_id, dist_nueva, dist_provista = distribuidora
    efectivos = {}
    for campo, valor in leidos.items():
        if valor is not None:
            efectivos[campo] = valor
        elif existente is not None:
            efectivos[campo] = getattr(existente, campo)
        else:
            efectivos[campo] = _DEFECTOS.get(campo)
    valores = {
        **efectivos,
        "stock_inicial": stock_inicial or 0,
        "distribuidora_id": dist_id,
        "distribuidora_nueva": dist_nueva,
    }
    # Los campos que ya fallaron se reemplazan por un valor valido para que
    # ProductoCreate no repita el mismo error (D8).
    datos = {**{k: v for k, v in efectivos.items() if v is not None}}
    datos["sku"] = codigo if codigo and "sku" not in fallidos else "X"
    datos.setdefault("nombre", "X")
    datos.setdefault("costo", Decimal("1"))
    _validar(acc, datos, fallidos)
    if existente is None:
        return _plan_fila(fila, codigo, acc, "crear", valores)
    cambios = [c for c in CAMPOS_ACTUALIZABLES if _distinto(c, efectivos[c], getattr(existente, c))]
    if dist_provista and (dist_nueva or dist_id != existente.distribuidora_id):
        cambios.append("distribuidora")
    if stock_inicial is not None and stock_inicial != existente.stock_actual:
        acc.aviso(
            "stock_inicial",
            f"el stock de la planilla ({stock_inicial}) no se aplica: el producto ya "
            f"tiene {existente.stock_actual}; corregilo con un ajuste de stock",
        )
    return _plan_fila(
        fila, codigo, acc, "actualizar" if cambios else "sin_cambios", valores,
        tuple(cambios), existente.id,
    )


def analizar(db: Session, planilla: Planilla, columnas: ResultadoColumnas) -> Plan:
    """Dry-run: la accion y los motivos de cada fila, sin escribir nada."""
    globales = (*planilla.errores, *columnas.errores)
    if globales:
        return Plan(errores_globales=globales)
    ctx = _foto(db)
    repetidos = _skus_repetidos(planilla.filas, columnas.indices)
    filas = tuple(_analizar_fila(f, columnas.indices, repetidos, ctx) for f in planilla.filas)
    nuevas = dict.fromkeys(
        f.valores["distribuidora_nueva"]
        for f in filas
        if f.accion is not None and f.valores.get("distribuidora_nueva")
    )
    return Plan(filas=filas, distribuidoras_a_crear=tuple(nuevas))
