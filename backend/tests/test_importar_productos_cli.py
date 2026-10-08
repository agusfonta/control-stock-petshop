"""CLI `python -m scripts.importar_productos` (C-08, tarea 9.3)."""

import json

import pytest
from sqlalchemy import func, select

from app.models import Distribuidora, MovimientoStock, Producto, Usuario
from scripts.generar_excel_prueba import generar
from scripts.importar_productos import main

DUENA = "duena@test.only"


@pytest.fixture
def planillas(tmp_path):
    limpia, sucia = generar(tmp_path / "ejemplos")
    return limpia, sucia


@pytest.fixture
def con_duena(db_session_factory):
    with db_session_factory() as db:
        db.add(Usuario(email=DUENA, password_hash="x", rol="duena"))
        db.commit()
    return db_session_factory


def conteos(factory):
    with factory() as db:
        cuenta = lambda m: db.scalar(select(func.count()).select_from(m))  # noqa: E731
        return cuenta(Producto), cuenta(MovimientoStock), cuenta(Distribuidora)


def test_analisis_de_la_sucia_imprime_filas_no_ok_sale_1_y_no_escribe(con_duena, planillas, capsys):
    codigo = main([str(planillas[1])], con_duena)
    salida = capsys.readouterr().out
    assert codigo == 1
    for fila in ("fila 7", "fila 8", "fila 9", "fila 11"):
        assert fila in salida
    assert "error" in salida and "advertencia" in salida
    assert "DUP-1" in salida
    assert conteos(con_duena) == (0, 0, 0)


def test_confirmar_la_limpia_crea_productos_y_aperturas_y_sale_0(con_duena, planillas, capsys):
    codigo = main([str(planillas[0]), "--confirmar"], con_duena)
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "Lote" in salida
    productos, movimientos, distribuidoras = conteos(con_duena)
    assert productos == 18 and movimientos == 17 and distribuidoras == 3  # un producto sin stock


def test_segunda_corrida_confirmada_deja_todo_sin_cambios(con_duena, planillas, capsys):
    main([str(planillas[0]), "--confirmar"], con_duena)
    antes = conteos(con_duena)
    capsys.readouterr()
    codigo = main([str(planillas[0]), "--confirmar"], con_duena)
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "sin cambios: 18" in salida
    assert conteos(con_duena) == antes


def test_confirmar_con_errores_no_escribe_y_sale_1(con_duena, planillas, capsys):
    assert main([str(planillas[1]), "--confirmar"], con_duena) == 1
    assert "No se aplico nada" in capsys.readouterr().out
    assert conteos(con_duena) == (0, 0, 0)


def test_mapeo_con_json_invalido_sale_2(con_duena, planillas):
    assert main([str(planillas[0]), "--mapeo", "{no es json"], con_duena) == 2
    assert main([str(planillas[0]), "--mapeo", '{"campo_raro": "X"}'], con_duena) == 2


def test_mapeo_valido_se_usa(con_duena, tmp_path, capsys):
    from tests.migracion_helpers import xlsx_bytes

    ruta = tmp_path / "raro.xlsx"
    ruta.write_bytes(xlsx_bytes(["id", "cosa", "Valor compra"], [["a-1", "Uno", 100]]))
    mapeo = json.dumps({"sku": "id", "nombre": "cosa", "costo": "Valor compra"})
    assert main([str(ruta), "--mapeo", mapeo], con_duena) == 0
    assert "Valor compra" in capsys.readouterr().out


def test_archivo_inexistente_sale_2(con_duena, tmp_path):
    assert main([str(tmp_path / "nada.xlsx")], con_duena) == 2


def test_formato_no_admitido_sale_2(con_duena, tmp_path):
    pdf = tmp_path / "catalogo.pdf"
    pdf.write_bytes(b"%PDF")
    assert main([str(pdf)], con_duena) == 2


def test_dos_duenas_sin_usuario_sale_2_sin_escribir(con_duena, planillas):
    with con_duena() as db:
        db.add(Usuario(email="otra@test.only", password_hash="x", rol="duena"))
        db.commit()
    assert main([str(planillas[0]), "--confirmar"], con_duena) == 2
    assert conteos(con_duena) == (0, 0, 0)


def test_usuario_explicito_desambigua_entre_duenas(con_duena, planillas):
    with con_duena() as db:
        db.add(Usuario(email="otra@test.only", password_hash="x", rol="duena"))
        db.commit()
    assert main([str(planillas[0]), "--confirmar", "--usuario", "otra@test.only"], con_duena) == 0
    with con_duena() as db:
        otra = db.scalar(select(Usuario).where(Usuario.email == "otra@test.only"))
        assert {m.usuario_id for m in db.scalars(select(MovimientoStock))} == {otra.id}


def test_usuario_mostrador_o_inexistente_sale_2(con_duena, planillas):
    with con_duena() as db:
        db.add(Usuario(email="m@test.only", password_hash="x", rol="mostrador"))
        db.commit()
    assert main([str(planillas[0]), "--usuario", "m@test.only"], con_duena) == 2
    assert main([str(planillas[0]), "--usuario", "nadie@test.only"], con_duena) == 2


def test_sin_ninguna_duena_activa_sale_2(db_session_factory, planillas):
    assert main([str(planillas[0])], db_session_factory) == 2
