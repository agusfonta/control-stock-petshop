"""Aplicacion todo-o-nada e `importar()` (C-08, D4/D5/D6)."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Distribuidora, MovimientoStock, Producto, Usuario
from app.services.migracion import importar
from tests.migracion_helpers import xlsx_bytes

D = Decimal
ENC = ["sku", "nombre", "costo", "margen_pct", "stock", "distribuidora"]
FILAS_OK = [
    ["bal-1", "Balanceado", 1000, 35, 20, "Distribuidora Sur"],
    ["PIP-2", "Pipeta", "$ 3.200,50", "50%", 30, "distribuidora  sur"],
    ["JUG-3", "Juguete", 1500, 60, 0, "Norte"],
    ["COL-4", "Collar", 800, 40, None, None],
]


@pytest.fixture
def db(db_session_factory):
    with db_session_factory() as session:
        yield session


@pytest.fixture
def duena(db):
    u = Usuario(email="d@test.only", password_hash="x", rol="duena")
    db.add(u)
    db.commit()
    return u


def archivo(filas=FILAS_OK, enc=ENC):
    return xlsx_bytes(enc, filas)


def conteos(db):
    cuenta = lambda m: db.scalar(select(func.count()).select_from(m))  # noqa: E731
    return cuenta(Producto), cuenta(MovimientoStock), cuenta(Distribuidora)


def correr(db, duena, filas=FILAS_OK, confirmar=True, nombre="lote.xlsx", enc=ENC, **kw):
    return importar(db, archivo(filas, enc), nombre, duena, confirmar=confirmar, **kw)


def test_dry_run_devuelve_reporte_sin_lote_y_no_escribe(db, duena):
    reporte = correr(db, duena, confirmar=False)
    assert reporte.confirmado is False and reporte.lote_id is None
    assert reporte.totales.crear == 4 and reporte.totales.errores == 0
    assert reporte.distribuidoras_a_crear == ["Distribuidora Sur", "Norte"]
    assert conteos(db) == (0, 0, 0)


def test_confirmar_crea_productos_con_sku_en_mayusculas_y_precio(db, duena):
    reporte = correr(db, duena)
    assert reporte.confirmado is True and len(reporte.lote_id) == 36
    productos = {p.sku: p for p in db.scalars(select(Producto))}
    assert sorted(productos) == ["BAL-1", "COL-4", "JUG-3", "PIP-2"]
    assert productos["BAL-1"].precio_venta == D("1350.00")
    assert productos["PIP-2"].costo == D("3200.50")
    assert productos["PIP-2"].margen_pct == D("0.5")


def test_confirmar_crea_una_distribuidora_por_nombre_y_la_asigna_como_default(db, duena):
    correr(db, duena)
    nombres = sorted(d.nombre for d in db.scalars(select(Distribuidora)))
    assert nombres == ["Distribuidora Sur", "Norte"]
    por_sku = {p.sku: p for p in db.scalars(select(Producto))}
    assert por_sku["BAL-1"].distribuidora_default_id == por_sku["PIP-2"].distribuidora_default_id
    assert por_sku["JUG-3"].distribuidora_default_id != por_sku["BAL-1"].distribuidora_default_id
    assert por_sku["COL-4"].distribuidora_default_id is None


def test_stock_inicial_es_un_movimiento_apertura_con_el_lote(db, duena):
    reporte = correr(db, duena, nombre="catalogo.xlsx")
    movs = {
        db.get(Producto, m.producto_id).sku: m for m in db.scalars(select(MovimientoStock))
    }
    assert sorted(movs) == ["BAL-1", "PIP-2"]  # stock 0 o vacio: sin movimiento
    m = movs["BAL-1"]
    assert (m.tipo, m.cantidad, m.stock_previo, m.stock_nuevo) == ("apertura", 20, 0, 20)
    assert m.usuario_id == duena.id and m.ref_id == reporte.lote_id
    assert "catalogo.xlsx" in m.motivo
    stock = {p.sku: p.stock_actual for p in db.scalars(select(Producto))}
    assert stock == {"BAL-1": 20, "PIP-2": 30, "JUG-3": 0, "COL-4": 0}


def test_existente_actualiza_costo_sin_tocar_stock_ni_crear_movimiento(db, duena):
    db.add(Producto(sku="BAL-1", nombre="Viejo", costo=D("500"), margen_pct=D("0.2"),
                    stock_actual=5))
    db.commit()
    reporte = correr(db, duena, filas=[["bal-1", "Balanceado", 1000, 35, 20, None]])
    fila = reporte.filas[0]
    assert fila.accion == "actualizar" and "costo" in fila.campos_cambiados
    assert fila.estado == "advertencia"  # stock de la planilla ignorado
    p = db.scalars(select(Producto)).one()
    assert (p.costo, p.margen_pct, p.nombre, p.stock_actual) == (D("1000"), D("0.35"), "Balanceado", 5)
    assert p.sku == "BAL-1"  # no se pisa la grafia existente
    assert conteos(db) == (1, 0, 0)


def test_confirmar_con_una_fila_error_no_escribe_y_devuelve_el_reporte(db, duena):
    filas = [*FILAS_OK, ["MAL-5", "Sin costo", 0, 10, 1, None]]
    reporte = correr(db, duena, filas=filas)
    assert reporte.confirmado is False and reporte.lote_id is None
    assert reporte.totales.errores == 1
    assert [f.fila for f in reporte.filas if f.estado == "error"] == [6]
    assert conteos(db) == (0, 0, 0)


def test_errores_globales_bloquean_la_confirmacion(db, duena):
    reporte = correr(db, duena, filas=[["A", "x", 1]], enc=["sku", "nombre", "nada"])
    assert reporte.confirmado is False
    assert reporte.errores_globales == ["falta columna obligatoria: costo"]
    assert reporte.filas == [] and conteos(db) == (0, 0, 0)


def test_reconfirmar_el_mismo_archivo_es_idempotente(db, duena):
    correr(db, duena)
    antes = conteos(db)
    reporte = correr(db, duena)
    assert reporte.confirmado is True
    assert {f.accion for f in reporte.filas} == {"sin_cambios"}
    assert conteos(db) == antes == (4, 2, 2)


def test_archivo_demasiado_grande_levanta_antes_de_leer(db, duena, monkeypatch):
    from app.services import migracion

    monkeypatch.setattr(migracion, "MAX_BYTES", 10)
    with pytest.raises(migracion.ArchivoDemasiadoGrande):
        importar(db, b"x" * 11, "enorme.xlsx", duena)


def test_formato_no_admitido_se_propaga(db, duena):
    from app.services.migracion.lectura import ArchivoNoAdmitido

    with pytest.raises(ArchivoNoAdmitido):
        importar(db, b"%PDF", "catalogo.pdf", duena)


def test_falla_a_mitad_de_la_aplicacion_no_persiste_nada(db, duena, monkeypatch):
    from app.services.migracion import aplicar as modulo

    real = modulo.aplicar_movimiento
    llamadas = []

    def falla_en_la_tercera(*args, **kwargs):
        llamadas.append(1)
        if len(llamadas) == 3:
            raise RuntimeError("falla simulada")
        return real(*args, **kwargs)

    monkeypatch.setattr(modulo, "aplicar_movimiento", falla_en_la_tercera)
    filas = [["A-1", "Uno", 10, 10, 1, "Sur"], ["A-2", "Dos", 10, 10, 2, "Sur"],
             ["A-3", "Tres", 10, 10, 3, "Norte"], ["A-4", "Cuatro", 10, 10, 4, None]]
    with pytest.raises(RuntimeError, match="falla simulada"):
        correr(db, duena, filas=filas)
    assert len(llamadas) == 3
    assert conteos(db) == (0, 0, 0)


def test_sku_creado_en_paralelo_levanta_catalogo_cambio_y_revierte(db, duena, monkeypatch):
    from app.services import migracion

    real = migracion.analizar

    def analiza_y_luego_otro_crea_el_sku(*args, **kwargs):
        plan = real(*args, **kwargs)
        db.add(Producto(sku="A-2", nombre="Paralelo", costo=D("5"), margen_pct=D("0")))
        db.commit()  # otra sesion se adelanta entre el analisis y la aplicacion
        return plan

    monkeypatch.setattr(migracion, "analizar", analiza_y_luego_otro_crea_el_sku)
    filas = [["A-1", "Uno", 10, 10, 1, "Sur"], ["A-2", "Dos", 10, 10, 2, None]]
    with pytest.raises(migracion.CatalogoCambio):
        correr(db, duena, filas=filas)
    assert [p.sku for p in db.scalars(select(Producto))] == ["A-2"]
    assert conteos(db) == (1, 0, 0)


def test_aceptacion_con_la_plantilla_csv_del_proyecto(db, duena):
    from pathlib import Path

    plantilla = Path(__file__).resolve().parents[2] / "data" / "plantilla_productos.csv"
    contenido = plantilla.read_bytes()
    seco = importar(db, contenido, plantilla.name, duena)
    assert seco.errores_globales == [] and seco.totales.ok == 3 and seco.totales.filas == 3
    assert conteos(db) == (0, 0, 0)

    reporte = importar(db, contenido, plantilla.name, duena, confirmar=True)
    assert reporte.confirmado is True
    assert conteos(db) == (3, 3, 2)
    assert sorted(d.nombre for d in db.scalars(select(Distribuidora))) == [
        "Distribuidora Norte", "Distribuidora Sur",
    ]
    aperturas = sorted(m.cantidad for m in db.scalars(select(MovimientoStock)))
    assert aperturas == [12, 20, 30]
    assert {m.tipo for m in db.scalars(select(MovimientoStock))} == {"apertura"}
