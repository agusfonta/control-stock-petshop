"""Genera las planillas de ejemplo para probar la migracion (C-08, D11).

Determinista: datos fijos en este modulo y fechas de propiedades fijas, asi
regenerar produce las mismas celdas. Crea dos archivos:

- `productos_prueba.xlsx`: catalogo limpio, todas las filas validas.
- `productos_prueba_sucio.xlsx`: encabezados con alias, `$` y miles, coma
  decimal, margenes con `%`, espacios sobrantes, filas vacias y tres errores
  (SKU duplicado, costo 0 y stock con decimales).

Uso (desde backend/):
    python -m scripts.generar_excel_prueba [--salida <carpeta>]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

REPO_DIR = Path(__file__).resolve().parents[2]
SALIDA_DEFECTO = REPO_DIR / "docs" / "ejemplos"
FECHA_FIJA = datetime(2026, 1, 1, 12, 0, 0)

ENCABEZADOS_LIMPIA = [
    "sku", "nombre", "categoria", "marca", "distribuidora",
    "costo", "margen_pct", "stock_inicial", "stock_minimo", "unidad",
]
SUR, NORTE, PETFOOD = "Distribuidora Sur", "Distribuidora Norte", "PetFood Mayorista"
PRODUCTOS_LIMPIA = [
    ("BAL-ADU-15", "Balanceado adulto 15kg", "Alimentos", "Nutrican", SUR, 18500, 35, 20, 5, "bolsa"),
    ("BAL-CAC-15", "Balanceado cachorro 15kg", "Alimentos", "Nutrican", SUR, 21000, 35, 14, 5, "bolsa"),
    ("BAL-GAT-10", "Balanceado gato 10kg", "Alimentos", "Felix", PETFOOD, 16500, 38, 12, 4, "bolsa"),
    ("BAL-ADU-3", "Balanceado adulto 3kg", "Alimentos", "Nutrican", PETFOOD, 5200, 40, 30, 8, "bolsa"),
    ("SNK-HUE-500", "Snack huesitos 500g", "Alimentos", "PetFun", NORTE, 2500.5, 80, 40, 10, "unidad"),
    ("PIP-CAN-S", "Pipeta antiparasitaria canina S", "Antiparasitarios", "Zoovet", SUR, 2800, 50, 25, 10, "unidad"),
    ("PIP-CAN-M", "Pipeta antiparasitaria canina M", "Antiparasitarios", "Zoovet", SUR, 3200, 50, 30, 10, "unidad"),
    ("PIP-CAN-L", "Pipeta antiparasitaria canina L", "Antiparasitarios", "Zoovet", SUR, 3900, 50, 18, 8, "unidad"),
    ("COM-DES-6", "Comprimido desparasitante x6", "Antiparasitarios", "Zoovet", PETFOOD, 4100, 55, 16, 6, "caja"),
    ("JUG-SOG-ALG", "Juguete soga de algodon", "Juguetes", "PetFun", NORTE, 1500, 60, 12, 4, "unidad"),
    ("JUG-PEL-01", "Pelota resistente", "Juguetes", "PetFun", NORTE, 1200, 95, 50, 10, "unidad"),
    ("JUG-RAT-CAT", "Raton con catnip", "Juguetes", "CatJoy", NORTE, 900, 100, 33, 10, "unidad"),
    ("ACC-COL-M", "Collar nylon talle M", "Accesorios", "Trixie", NORTE, 2500, 100, 20, 5, "unidad"),
    ("ACC-COR-5M", "Correa retractil 5m", "Accesorios", "Trixie", NORTE, 8000, 85, 15, 5, "unidad"),
    ("ACC-PLA-ACE", "Plato acero inoxidable", "Accesorios", "Ferplast", SUR, 3000, 100, 18, 5, "unidad"),
    ("HIG-SHA-500", "Shampoo antipulgas 500ml", "Higiene", "Osmac", SUR, 4000, 90, 22, 6, "unidad"),
    ("HIG-PIE-4", "Piedras sanitarias 4kg", "Higiene", "Absorsol", PETFOOD, 3500, 90, 25, 10, "bolsa"),
    ("HIG-TOA-50", "Toallitas humedas x50", "Higiene", "PetCare", PETFOOD, 2000, 90, 0, 10, "caja"),
]

ENCABEZADOS_SUCIA = [
    "Código", "Descripción", "Rubro", "Proveedor", "Precio Costo",
    "Ganancia %", "Stock", "Stock mínimo", "Observaciones",
]
VACIA = [None] * len(ENCABEZADOS_SUCIA)
FILAS_SUCIA = [
    ["BAL-ADU-15 ", "  Balanceado adulto 15kg", "ALIMENTOS", "distribuidora  sur", "$ 18.500,50", "35%", 20, 5, "en oferta"],
    ["PIP-CAN-M", "Pipeta antiparasitaria M", "Antiparasitarios", "Distribuidora Sur", "$ 3.200", "50", 30, 10, None],
    VACIA,
    ["JUG-SOG-ALG", "Juguete soga de algodon", "Juguetes", "Distribuidora Norte", "1.500,00", 0.6, 12, 4, None],
    ["ACC COL M", "Collar nylon talle M", "Accesorios", "Distribuidora Norte", "2500", "0,35", 8, 2, "SKU con espacios"],
    ["DUP-1", "Producto repetido A", "Higiene", "Distribuidora Sur", "1000", "20", 5, 1, None],
    ["DUP-1", "Producto repetido B", "Higiene", "Distribuidora Sur", "1100", "20", 5, 1, None],
    ["SIN-COSTO", "Producto sin costo", "Higiene", "Distribuidora Sur", 0, "30", 4, 1, None],
    VACIA,
    ["STK-DEC", "Producto con stock decimal", "Higiene", "Distribuidora Sur", "800", "40", "2,5", 1, None],
    ["HIG-SHA-500", "Shampoo antipulgas 500ml", "Higiene", "PetFood Mayorista", "$ 4.000", "90%", 22, 6, None],
]
# (fila, columna) 1-based: el margen de JUG-SOG-ALG (0,6) es una celda con formato porcentaje.
FORMATOS_SUCIA = {(5, 6): "0%"}


def _guardar(ruta: Path, encabezados: list, filas: list, formatos: dict | None = None) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Productos"
    ws.append(encabezados)
    for fila in filas:
        ws.append(list(fila))
    for (f, c), formato in (formatos or {}).items():
        ws.cell(f, c).number_format = formato
    wb.properties.creator = "generar_excel_prueba"
    wb.properties.created = FECHA_FIJA
    wb.properties.modified = FECHA_FIJA
    wb.save(ruta)


def generar(salida: Path) -> list[Path]:
    """Escribe las dos planillas en `salida` (la crea si no existe)."""
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    limpia = salida / "productos_prueba.xlsx"
    sucia = salida / "productos_prueba_sucio.xlsx"
    _guardar(limpia, ENCABEZADOS_LIMPIA, PRODUCTOS_LIMPIA)
    _guardar(sucia, ENCABEZADOS_SUCIA, FILAS_SUCIA, FORMATOS_SUCIA)
    return [limpia, sucia]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera las planillas de ejemplo (C-08).")
    parser.add_argument("--salida", type=Path, default=SALIDA_DEFECTO, help="carpeta de salida")
    args = parser.parse_args(argv)
    for ruta in generar(args.salida):
        print(f"generado: {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
