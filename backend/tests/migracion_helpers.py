"""Helpers de C-08: arman planillas xlsx/csv en memoria para los tests."""

from io import BytesIO

from openpyxl import Workbook


def xlsx_bytes(
    encabezados: list[object],
    filas: list[list[object]],
    formatos: dict[tuple[int, int], str] | None = None,
    hoja: str = "Hoja1",
) -> bytes:
    """Arma un xlsx en memoria.

    `formatos` mapea (fila, columna) 1-based -> `number_format` de la celda.
    Los strings que empiezan con `=` quedan como formulas sin valor cacheado.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    ws.append(encabezados)
    for fila in filas:
        ws.append(fila)
    for (f, c), formato in (formatos or {}).items():
        ws.cell(f, c).number_format = formato
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


def csv_bytes(texto: str, encoding: str = "utf-8") -> bytes:
    """Codifica el texto de un csv con el encoding pedido."""
    return texto.encode(encoding)
