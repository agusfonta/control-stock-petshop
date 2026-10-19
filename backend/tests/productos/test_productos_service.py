"""Service de productos (C-16 D5): logica de acceso a datos fuera del router.

RED-first: el service no existe todavia. Los tests HTTP (`test_productos_*.py`)
son la caracterizacion del comportamiento; estos prueban el contrato del
service con excepciones de dominio (sin HTTP).
"""

from decimal import Decimal

import pytest

from app.modules.auth.models import Usuario
from app.modules.productos import service
from app.modules.productos.models import Producto
from app.modules.productos.schemas import MargenMinimoRequest, ProductoCreate, ProductoUpdate
from app.modules.stock.models import MovimientoStock


@pytest.fixture
def db(db_session_factory):
    with db_session_factory() as session:
        yield session


@pytest.fixture
def usuario(db) -> Usuario:
    user = Usuario(email="duena@test.only", password_hash="x", rol="duena")
    db.add(user)
    db.commit()
    return user


def _datos(**extra) -> ProductoCreate:
    base = {"sku": "SKU-001", "nombre": "Alimento Perro 20kg", "costo": Decimal("1000"), "margen_pct": Decimal("0.5")}
    base.update(extra)
    return ProductoCreate(**base)


def _crear(db, usuario, **extra) -> Producto:
    return service.crear_producto(db, _datos(**extra), usuario)


# --- crear ---


def test_crear_calcula_precio_venta_y_persiste(db, usuario) -> None:
    producto = _crear(db, usuario)

    assert producto.id
    assert producto.precio_venta == 1500  # 1000 * (1 + 0.5)
    assert producto.stock_actual == 0


def test_crear_con_stock_inicial_deja_movimiento_de_apertura(db, usuario) -> None:
    producto = _crear(db, usuario, stock_actual=7)

    assert producto.stock_actual == 7
    movs = db.query(MovimientoStock).filter_by(producto_id=producto.id).all()
    assert [(m.tipo, m.cantidad, m.motivo) for m in movs] == [("apertura", 7, "stock inicial")]


def test_crear_sin_stock_inicial_no_genera_movimientos(db, usuario) -> None:
    producto = _crear(db, usuario, stock_actual=0)

    assert db.query(MovimientoStock).filter_by(producto_id=producto.id).count() == 0


def test_crear_con_sku_duplicado_lanza_sku_duplicado(db, usuario) -> None:
    _crear(db, usuario)

    with pytest.raises(service.SkuDuplicado):
        _crear(db, usuario, nombre="Otro")


def test_crear_con_sku_duplicado_no_deja_filas_extra(db, usuario) -> None:
    _crear(db, usuario, stock_actual=3)

    with pytest.raises(service.SkuDuplicado):
        _crear(db, usuario, stock_actual=5)

    assert db.query(Producto).count() == 1
    assert db.query(MovimientoStock).count() == 1


# --- obtener ---


def test_obtener_devuelve_el_producto(db, usuario) -> None:
    creado = _crear(db, usuario)

    assert service.obtener_producto(db, creado.id).sku == "SKU-001"


def test_obtener_inexistente_lanza_producto_no_encontrado(db) -> None:
    with pytest.raises(service.ProductoNoEncontrado):
        service.obtener_producto(db, "no-existe")


def test_obtener_no_filtra_inactivos(db, usuario) -> None:
    creado = _crear(db, usuario)
    service.desactivar_producto(db, creado.id)

    assert service.obtener_producto(db, creado.id).activo is False


# --- listar / buscar ---


def test_listar_pagina_activos_y_cuenta_el_total(db, usuario) -> None:
    for n in range(3):
        _crear(db, usuario, sku=f"SKU-{n}", nombre=f"Prod {n}")
    baja = _crear(db, usuario, sku="SKU-BAJA", nombre="Baja")
    service.desactivar_producto(db, baja.id)

    items, total = service.listar_productos(db, 1, 2)
    resto, _ = service.listar_productos(db, 2, 2)

    assert total == 3
    assert len(items) == 2
    assert len(resto) == 1


def test_listar_sin_productos_devuelve_vacio(db) -> None:
    assert service.listar_productos(db, 1, 20) == ([], 0)


def test_buscar_por_sku_exacto(db, usuario) -> None:
    _crear(db, usuario, sku="ABC-1", nombre="Uno")
    _crear(db, usuario, sku="ABC-12", nombre="Dos")

    items, total = service.buscar_productos(db, "ABC-1", 1, 20)

    assert total == 1
    assert items[0].sku == "ABC-1"


def test_buscar_por_nombre_parcial_sin_distinguir_mayusculas_ordenado(db, usuario) -> None:
    _crear(db, usuario, sku="B", nombre="Alimento Gato")
    _crear(db, usuario, sku="A", nombre="Alimento Perro")
    _crear(db, usuario, sku="C", nombre="Juguete")

    items, total = service.buscar_productos(db, "alimento", 1, 20)

    assert total == 2
    assert [p.nombre for p in items] == ["Alimento Gato", "Alimento Perro"]


def test_buscar_excluye_inactivos(db, usuario) -> None:
    baja = _crear(db, usuario, sku="X", nombre="Alimento viejo")
    service.desactivar_producto(db, baja.id)

    assert service.buscar_productos(db, "alimento", 1, 20) == ([], 0)


# --- actualizar ---


def test_actualizar_aplica_campos_enviados_y_recalcula_precio(db, usuario) -> None:
    creado = _crear(db, usuario)

    actualizado = service.actualizar_producto(db, creado.id, ProductoUpdate(costo=Decimal("2000")))

    assert actualizado.costo == 2000
    assert actualizado.precio_venta == 3000
    assert actualizado.nombre == "Alimento Perro 20kg"


def test_actualizar_inexistente_lanza_producto_no_encontrado(db) -> None:
    with pytest.raises(service.ProductoNoEncontrado):
        service.actualizar_producto(db, "no-existe", ProductoUpdate(nombre="X"))


def test_actualizar_a_sku_de_otro_lanza_sku_duplicado(db, usuario) -> None:
    _crear(db, usuario, sku="UNO", nombre="Uno")
    dos = _crear(db, usuario, sku="DOS", nombre="Dos")

    with pytest.raises(service.SkuDuplicado):
        service.actualizar_producto(db, dos.id, ProductoUpdate(sku="UNO"))


def test_actualizar_con_su_propio_sku_no_choca(db, usuario) -> None:
    uno = _crear(db, usuario, sku="UNO")

    actualizado = service.actualizar_producto(db, uno.id, ProductoUpdate(sku="UNO", nombre="Uno B"))

    assert actualizado.nombre == "Uno B"


# --- margen minimo ---


def test_actualizar_margen_minimo_cambia_margen_y_precio(db, usuario) -> None:
    creado = _crear(db, usuario)

    actualizado = service.actualizar_margen_minimo(db, creado.id, MargenMinimoRequest(margen_pct=Decimal("1")))

    assert actualizado.margen_pct == 1
    assert actualizado.precio_venta == 2000


def test_actualizar_margen_minimo_cambia_solo_stock_minimo(db, usuario) -> None:
    creado = _crear(db, usuario)

    actualizado = service.actualizar_margen_minimo(db, creado.id, MargenMinimoRequest(stock_minimo=9))

    assert actualizado.stock_minimo == 9
    assert actualizado.margen_pct == Decimal("0.5")


def test_actualizar_margen_minimo_inexistente_lanza_producto_no_encontrado(db) -> None:
    with pytest.raises(service.ProductoNoEncontrado):
        service.actualizar_margen_minimo(db, "no-existe", MargenMinimoRequest(stock_minimo=1))


# --- desactivar ---


def test_desactivar_hace_soft_delete(db, usuario) -> None:
    creado = _crear(db, usuario)

    service.desactivar_producto(db, creado.id)

    assert db.get(Producto, creado.id).activo is False
    assert service.listar_productos(db, 1, 20)[1] == 0


def test_desactivar_inexistente_lanza_producto_no_encontrado(db) -> None:
    with pytest.raises(service.ProductoNoEncontrado):
        service.desactivar_producto(db, "no-existe")
