"""CLI para migrar el catalogo desde un Excel/CSV (C-08, D1/D11).

Por defecto solo ANALIZA (dry-run) e imprime el reporte; aplica unicamente con
`--confirmar`. Todo-o-nada: una fila con error bloquea la confirmacion.

Codigos de salida: 0 sin errores, 1 errores de datos, 2 uso invalido o
usuario no resoluble.

Uso (desde backend/):
    python -m scripts.importar_productos ../docs/ejemplos/productos_prueba.xlsx
    python -m scripts.importar_productos catalogo.xlsx --mapeo mapeo.json --confirmar
"""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Usuario
from app.schemas import MapeoColumnas, ReporteImportacion
from app.services.migracion import (
    ArchivoDemasiadoGrande,
    ArchivoNoAdmitido,
    CatalogoCambio,
    importar,
)

USO, ERROR_DATOS, OK = 2, 1, 0


class UsoInvalido(Exception):
    """Argumentos o usuario no resolubles (codigo de salida 2)."""


def _mapeo(crudo: str | None) -> dict[str, str] | None:
    """`--mapeo` acepta un JSON inline o la ruta de un archivo .json."""
    if not crudo:
        return None
    ruta = Path(crudo)
    try:
        texto = ruta.read_text(encoding="utf-8-sig") if ruta.is_file() else crudo
        return MapeoColumnas.model_validate(json.loads(texto)).a_dict()
    except (json.JSONDecodeError, ValidationError, OSError) as exc:
        raise UsoInvalido(f"--mapeo invalido: {exc}") from None


def _resolver_usuario(db: Session, email: str | None) -> Usuario:
    duenas = db.scalars(
        select(Usuario).where(Usuario.rol == "duena", Usuario.activo.is_(True))
    ).all()
    if email:
        elegida = next((u for u in duenas if u.email.lower() == email.strip().lower()), None)
        if elegida is None:
            raise UsoInvalido(f"--usuario {email}: no es una duena activa")
        return elegida
    if len(duenas) != 1:
        raise UsoInvalido(
            "no hay una unica duena activa "
            f"({len(duenas)}); indica cual con --usuario <email>"
        )
    return duenas[0]


def _imprimir(r: ReporteImportacion) -> None:
    t = r.totales
    print(f"Archivo: {r.archivo}")
    for error in r.errores_globales:
        print(f"ERROR GLOBAL: {error}")
    if r.columnas.mapeadas:
        print("Columnas: " + ", ".join(f"{c} <- {h}" for c, h in r.columnas.mapeadas.items()))
    if r.columnas.ignoradas:
        print("Columnas ignoradas: " + ", ".join(r.columnas.ignoradas))
    print(f"Filas: {t.filas} (ok {t.ok}, advertencias {t.advertencias}, errores {t.errores})")
    print(f"A crear: {t.crear} | a actualizar: {t.actualizar} | sin cambios: {t.sin_cambios}")
    print(f"Distribuidoras a crear: {t.distribuidoras_a_crear} | unidades de apertura: {t.unidades_apertura}")
    for nueva in r.distribuidoras_a_crear:
        print(f"  distribuidora nueva: {nueva}")
    for fila in r.filas:
        if fila.estado == "ok":
            continue
        print(f"  fila {fila.fila} [{fila.estado}] {fila.sku or '(sin SKU)'}")
        for m in fila.motivos:
            print(f"      {m.gravedad}: {m.campo or 'general'}: {m.mensaje}")


def _correr(args: argparse.Namespace, db: Session) -> int:
    ruta = Path(args.archivo)
    if not ruta.is_file():
        raise UsoInvalido(f"no existe el archivo: {ruta}")
    mapeo = _mapeo(args.mapeo)
    usuario = _resolver_usuario(db, args.usuario)
    try:
        reporte = importar(
            db, ruta.read_bytes(), ruta.name, usuario,
            confirmar=args.confirmar, mapeo=mapeo, hoja=args.hoja,
        )
    except (ArchivoNoAdmitido, ArchivoDemasiadoGrande) as exc:
        raise UsoInvalido(str(exc)) from None
    except CatalogoCambio as exc:
        print(f"No se aplico nada: {exc}")
        return ERROR_DATOS
    _imprimir(reporte)
    con_errores = bool(reporte.errores_globales) or reporte.totales.errores > 0
    if reporte.confirmado:
        print(f"Importacion aplicada. Lote: {reporte.lote_id}")
    elif args.confirmar:
        print("No se aplico nada: corregi las filas con error y volve a correr.")
    elif not con_errores:
        print("Analisis sin errores. Para aplicar, volve a correr con --confirmar.")
    return ERROR_DATOS if con_errores else OK


def main(argv: list[str] | None = None, session_factory: Callable[[], Session] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Importa productos desde .xlsx/.csv (analiza por defecto).")
    parser.add_argument("archivo", help="planilla .xlsx o .csv")
    parser.add_argument("--confirmar", action="store_true", help="aplicar la importacion (sin esto solo analiza)")
    parser.add_argument("--mapeo", help="JSON {campo: encabezado} o ruta a un .json")
    parser.add_argument("--hoja", help="hoja del xlsx (por defecto, la primera)")
    parser.add_argument("--usuario", help="email de la duena que importa (por defecto, la unica activa)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse sale con 2 ante uso invalido
        return int(exc.code or 0)
    if session_factory is None:
        from app.core.db import SessionLocal as session_factory
    try:
        with session_factory() as db:
            return _correr(args, db)
    except UsoInvalido as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return USO


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
