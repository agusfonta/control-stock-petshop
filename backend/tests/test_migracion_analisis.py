"""Analisis / dry-run de planillas contra la base (C-08, D3/D5/D7/D8/D9)."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Distribuidora, MovimientoStock, Producto
from app.services.migracion.analisis import analizar
from app.services.migracion.columnas import resolver_columnas
from app.services.migracion.lectura import leer_planilla
from tests.migracion_helpers import xlsx_bytes

D = Decimal
ENC = ["sku", "nombre", "costo", "margen_pct"]


@pytest.fixture
def db(db_session_factory):
    with db_session_factory() as session:
        yield session


def correr(db, encabezados, filas, formatos=None, mapeo=None):
    planilla = leer_planilla(xlsx_bytes(encabezados, filas, formatos), "t.xlsx")
    return analizar(db, planilla, resolver_columnas(planilla.encabezados, mapeo))


def motivos(fila, gravedad=None):
    return [(m.campo, m.mensaje) for m in fila.motivos if gravedad in (None, m.gravedad)]


def test_filas_validas_nuevas_son_ok_y_se_crean(db):
    plan = correr(db, ENC, [["a-1", "Uno", 100, 35], ["A-2", "Dos", "$ 1.250,50", "50%"]])
    assert [(f.fila, f.sku, f.estado, f.accion) for f in plan.filas] == [
        (2, "A-1", "ok", "crear"),
        (3, "A-2", "ok", "crear"),
    ]
    assert plan.filas[1].valores["costo"] == D("1250.50")
    assert plan.filas[1].valores["margen_pct"] == D("0.5")
    assert plan.errores_globales == ()


@pytest.mark.parametrize("costo", [0, None, "0", "-5"])
def test_costo_cero_vacio_o_negativo_es_error_en_costo_con_su_fila(db, costo):
    plan = correr(db, ENC, [["A-1", "Uno", 100, 10], ["A-2", "Dos", costo, 10]])
    fila = plan.filas[1]
    assert (fila.fila, fila.estado, fila.accion) == (3, "error", None)
    assert motivos(fila, "error")[0][0] == "costo"
    assert plan.filas[0].estado == "ok"


def test_stock_con_decimales_es_error(db):
    plan = correr(db, [*ENC, "stock"], [["A-1", "Uno", 100, 10, "2,5"]])
    assert plan.filas[0].estado == "error"
    assert motivos(plan.filas[0], "error")[0][0] == "stock_inicial"


def test_sku_con_formato_invalido_es_error_en_castellano(db):
    plan = correr(db, ENC, [["ABC/1", "Uno", 100, 10]])
    (campo, mensaje), = motivos(plan.filas[0], "error")
    assert campo == "sku"
    assert "letras" in mensaje


def test_nombre_demasiado_largo_es_error(db):
    plan = correr(db, ENC, [["A-1", "x" * 201, 100, 10]])
    (campo, mensaje), = motivos(plan.filas[0], "error")
    assert campo == "nombre" and "200" in mensaje


def test_nombre_vacio_en_producto_nuevo_es_error(db):
    plan = correr(db, ENC, [["A-1", None, 100, 10]])
    assert motivos(plan.filas[0], "error")[0][0] == "nombre"


def test_sku_repetido_marca_todas_las_apariciones_citandose(db):
    filas = [["A-1", "Uno", 1, 1], ["B-1", "B", 1, 1], ["B-2", "B2", 1, 1],
             ["a-1", "Uno bis", 1, 1], ["B-3", "B3", 1, 1]]
    plan = correr(db, ENC, filas)
    primera, cuarta = plan.filas[0], plan.filas[3]
    assert primera.estado == cuarta.estado == "error"
    assert "fila 5" in motivos(primera, "error")[0][1]
    assert "fila 2" in motivos(cuarta, "error")[0][1]
    assert plan.filas[1].estado == "ok"


def test_sin_margen_con_precio_deriva_el_margen_con_advertencia(db):
    plan = correr(db, ["sku", "nombre", "costo", "precio_venta"], [["A-1", "Uno", 1000, 1350]])
    fila = plan.filas[0]
    assert (fila.estado, fila.accion) == ("advertencia", "crear")
    assert fila.valores["margen_pct"] == D("0.35")
    assert motivos(fila, "advertencia")[0][0] == "margen_pct"


def test_precio_menor_al_costo_sin_margen_es_error(db):
    plan = correr(db, ["sku", "nombre", "costo", "precio_venta"], [["A-1", "Uno", 1000, 900]])
    assert plan.filas[0].estado == "error"
    assert motivos(plan.filas[0], "error")[0][0] == "precio_venta"


def test_sin_margen_ni_precio_usa_cero_con_advertencia(db):
    plan = correr(db, ["sku", "nombre", "costo"], [["A-1", "Uno", 1000]])
    fila = plan.filas[0]
    assert (fila.estado, fila.valores["margen_pct"]) == ("advertencia", D("0"))


def test_margen_y_precio_discordantes_advierten_y_gana_el_margen(db):
    plan = correr(db, [*ENC, "precio_venta"], [["A-1", "Uno", 1000, 35, 2000]])
    fila = plan.filas[0]
    assert fila.estado == "advertencia"
    assert fila.valores["margen_pct"] == D("0.35")


def test_margen_con_formato_porcentaje_y_advertencia_de_margen_bajo(db):
    plan = correr(db, ENC, [["A-1", "Uno", 100, 0.35], ["A-2", "Dos", 100, "0,35"]],
                  formatos={(2, 4): "0%"})
    assert plan.filas[0].valores["margen_pct"] == D("0.35")
    assert plan.filas[0].estado == "ok"
    assert plan.filas[1].estado == "advertencia"


def test_unidad_se_normaliza_y_una_desconocida_es_error(db):
    plan = correr(db, [*ENC, "unidad"], [["A-1", "Uno", 1, 1, "Bolsa"],
                                         ["A-2", "Dos", 1, 1, "litro"],
                                         ["A-3", "Tres", 1, 1, None]])
    assert plan.filas[0].valores["unidad"] == "bolsa"
    assert plan.filas[1].estado == "error"
    assert motivos(plan.filas[1], "error")[0][0] == "unidad"
    assert plan.filas[2].valores["unidad"] == "unidad"


def test_formula_sin_valor_en_costo_es_error_que_pide_guardar_en_excel(db):
    plan = correr(db, ENC, [["A-1", "Uno", "=10*2", 10]])
    (campo, mensaje), = motivos(plan.filas[0], "error")
    assert campo == "costo"
    assert "Excel" in mensaje


def test_errores_globales_de_columnas_o_planilla_no_analizan_filas(db):
    planilla = leer_planilla(xlsx_bytes(["sku", "nombre"], [["A-1", "Uno"]]), "t.xlsx")
    plan = analizar(db, planilla, resolver_columnas(planilla.encabezados, None))
    assert plan.filas == ()
    assert plan.errores_globales == ("falta columna obligatoria: costo",)


def test_costo_que_no_entra_en_la_columna_de_la_base_es_error(db):
    plan = correr(db, ENC, [["A-1", "Uno", "100.000.000,00", 10]])
    assert motivos(plan.filas[0], "error")[0][0] == "costo"


# --- contra datos existentes (6.3) -------------------------------------------

def crear_producto(db, sku="A-1", **kw):
    datos = dict(nombre="Uno", costo=D("1000"), margen_pct=D("0.35"), stock_actual=0)
    p = Producto(sku=sku, **{**datos, **kw})
    db.add(p)
    db.commit()
    return p


def crear_distribuidora(db, nombre="Distribuidora Sur", activo=True):
    d = Distribuidora(nombre=nombre, activo=activo)
    db.add(d)
    db.commit()
    return d


def test_existente_con_los_mismos_valores_es_sin_cambios(db):
    crear_producto(db)
    fila = correr(db, ENC, [["A-1", "Uno", 1000, 35]]).filas[0]
    assert (fila.estado, fila.accion, fila.campos_cambiados) == ("ok", "sin_cambios", ())


def test_existente_con_costo_distinto_se_actualiza_y_lista_el_campo(db):
    p = crear_producto(db)
    fila = correr(db, ENC, [["A-1", "Uno", 1200, 35]]).filas[0]
    assert (fila.accion, fila.campos_cambiados) == ("actualizar", ("costo",))
    assert fila.valores["costo"] == D("1200")
    assert fila.producto_id == p.id


def test_celdas_vacias_en_existente_no_son_cambios_ni_errores(db):
    crear_producto(db)
    fila = correr(db, ENC, [["A-1", None, None, None]]).filas[0]
    assert (fila.estado, fila.accion, fila.campos_cambiados) == ("ok", "sin_cambios", ())
    assert fila.valores["margen_pct"] == D("0.35")


def test_sku_existente_en_otra_caja_es_el_mismo_producto(db):
    p = crear_producto(db, sku="bal-adu-15")
    fila = correr(db, ENC, [["BAL-ADU-15", "Uno", 1000, 35]]).filas[0]
    assert (fila.accion, fila.producto_id) == ("sin_cambios", p.id)


def test_dos_productos_que_difieren_solo_en_mayusculas_son_ambiguos(db):
    crear_producto(db, sku="abc")
    crear_producto(db, sku="ABC")
    fila = correr(db, ENC, [["ABC", "Uno", 1000, 35]]).filas[0]
    assert fila.estado == "error"
    assert motivos(fila, "error")[0][0] == "sku"


def test_producto_dado_de_baja_es_error(db):
    crear_producto(db, activo=False)
    fila = correr(db, ENC, [["A-1", "Uno", 1000, 35]]).filas[0]
    (campo, mensaje), = motivos(fila, "error")
    assert campo == "sku" and "dado de baja" in mensaje


def test_stock_de_la_planilla_distinto_en_existente_advierte_y_no_cambia(db):
    crear_producto(db, stock_actual=5)
    plan = correr(db, [*ENC, "stock"], [["A-1", "Uno", 1000, 35, 12]])
    fila = plan.filas[0]
    assert (fila.estado, fila.accion) == ("advertencia", "sin_cambios")
    (campo, mensaje), = motivos(fila, "advertencia")
    assert campo == "stock_inicial" and "ajuste" in mensaje
    assert "stock_inicial" not in fila.campos_cambiados
    igual = correr(db, [*ENC, "stock"], [["A-1", "Uno", 1000, 35, 5]]).filas[0]
    assert igual.estado == "ok"


def test_distribuidora_inexistente_repetida_se_planifica_una_sola_vez(db):
    filas = [[f"A-{i}", "N", 1, 1, "Distribuidora Sur" if i % 2 == 0 else "distribuidora  SUR"]
             for i in range(5)]
    plan = correr(db, [*ENC, "distribuidora"], filas)
    assert plan.distribuidoras_a_crear == ("Distribuidora Sur",)
    assert all(f.valores["distribuidora_id"] is None for f in plan.filas)
    assert {f.valores["distribuidora_nueva"] for f in plan.filas} == {"Distribuidora Sur"}


def test_distribuidora_existente_con_otra_grafia_se_reutiliza(db):
    d = crear_distribuidora(db)
    fila = correr(db, [*ENC, "distribuidora"], [["A-1", "N", 1, 1, "distribuidora  sur"]])
    assert fila.distribuidoras_a_crear == ()
    assert fila.filas[0].valores["distribuidora_id"] == d.id


def test_distribuidora_homonima_o_solo_inactiva_es_error(db):
    crear_distribuidora(db, "Norte")
    crear_distribuidora(db, "NORTE")
    crear_distribuidora(db, "Vieja", activo=False)
    plan = correr(db, [*ENC, "distribuidora"], [["A-1", "N", 1, 1, "norte"],
                                                ["A-2", "N", 1, 1, "Vieja"]])
    assert [f.estado for f in plan.filas] == ["error", "error"]
    assert all(motivos(f, "error")[0][0] == "distribuidora" for f in plan.filas)
    assert plan.distribuidoras_a_crear == ()


def test_distribuidora_en_existente_cuenta_como_cambio(db):
    d = crear_distribuidora(db)
    crear_producto(db)
    fila = correr(db, [*ENC, "distribuidora"], [["A-1", "Uno", 1000, 35, "Distribuidora Sur"]]).filas[0]
    assert (fila.accion, fila.campos_cambiados) == ("actualizar", ("distribuidora",))
    assert fila.valores["distribuidora_id"] == d.id


def test_categoria_reutiliza_la_grafia_existente_o_la_primera_del_archivo(db):
    crear_producto(db, sku="X-1", categoria="Alimentos")
    plan = correr(db, [*ENC, "categoria"], [["A-1", "N", 1, 1, "ALIMENTOS"],
                                            ["A-2", "N", 1, 1, "JUGUETES"],
                                            ["A-3", "N", 1, 1, "Juguetes"]])
    assert [f.valores["categoria"] for f in plan.filas] == ["Alimentos", "JUGUETES", "JUGUETES"]


def test_totales_del_plan(db):
    crear_producto(db, sku="E-1")
    crear_producto(db, sku="E-2", costo=D("50"))
    plan = correr(db, [*ENC, "stock", "distribuidora"], [
        ["N-1", "N", 10, 10, 20, "Sur"],         # crear ok, 20 de apertura
        ["N-2", "N", 10, 10, 12, "Sur"],         # crear ok, 12 de apertura
        ["E-1", "Uno", 1000, 35, None, None],    # sin_cambios
        ["E-2", "Uno", 1000, 35, None, None],    # actualizar (costo)
        ["N-3", "N", 0, 10, 99, "Norte"],        # error: no suma apertura ni distribuidora
    ])
    t = plan.totales
    assert (t.filas, t.ok, t.advertencias, t.errores) == (5, 4, 0, 1)
    assert (t.crear, t.actualizar, t.sin_cambios) == (2, 1, 1)
    assert (t.distribuidoras_a_crear, t.unidades_apertura) == (1, 32)
    assert plan.hay_errores is True


def test_analizar_no_escribe_en_la_base(db):
    crear_producto(db, sku="E-1")
    antes = [db.scalar(select(func.count()).select_from(m))
             for m in (Producto, MovimientoStock, Distribuidora)]
    correr(db, [*ENC, "stock", "distribuidora"],
           [["N-1", "N", 10, 10, 20, "Nueva"], ["E-1", "Uno", 5, 5, 3, "Otra"]])
    despues = [db.scalar(select(func.count()).select_from(m))
               for m in (Producto, MovimientoStock, Distribuidora)]
    assert antes == despues == [1, 0, 0]
    assert not db.new and not db.dirty
