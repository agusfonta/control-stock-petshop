"""Service de distribuidoras (C-16 D5): logica de acceso a datos fuera del router.

RED-first: el service no existe todavia. Los tests HTTP (`test_distribuidoras*.py`)
son la caracterizacion del comportamiento; estos prueban el contrato del
service con excepciones de dominio (sin HTTP).
"""

from decimal import Decimal

import pytest

from app.modules.distribuidoras import service
from app.modules.distribuidoras.models import Distribuidora, ListaPrecio
from app.modules.distribuidoras.schemas import (
    DistribuidoraCreate,
    DistribuidoraUpdate,
    ListaPrecioDistribuidoraCreate,
    ListaPrecioUpdate,
)
from app.modules.productos.models import Producto


@pytest.fixture
def db(db_session_factory):
    with db_session_factory() as session:
        yield session


def _distribuidora(db, nombre="Distri Sur", **extra) -> Distribuidora:
    return service.crear_distribuidora(db, DistribuidoraCreate(nombre=nombre, **extra))


def _producto(db, sku="SKU-1", costo="1000", margen="0.5") -> Producto:
    producto = Producto(sku=sku, nombre=f"Prod {sku}", costo=Decimal(costo), margen_pct=Decimal(margen))
    db.add(producto)
    db.commit()
    return producto


def _lista(db, distribuidora, producto, costo="800") -> ListaPrecio:
    return service.agregar_a_lista(
        db,
        distribuidora.id,
        ListaPrecioDistribuidoraCreate(producto_id=producto.id, costo=Decimal(costo)),
    )


# --- crear / obtener ---


def test_crear_persiste_con_todos_los_campos(db) -> None:
    creada = _distribuidora(db, contacto="Juan", cuit="20-1", condiciones="30 dias")

    assert creada.id
    assert creada.activo is True
    assert (creada.contacto, creada.cuit, creada.condiciones) == ("Juan", "20-1", "30 dias")


def test_crear_dos_distribuidoras_con_el_mismo_nombre_es_valido(db) -> None:
    uno = _distribuidora(db)
    dos = _distribuidora(db)

    assert uno.id != dos.id


def test_obtener_devuelve_la_distribuidora(db) -> None:
    creada = _distribuidora(db)

    assert service.obtener_distribuidora(db, creada.id).nombre == "Distri Sur"


def test_obtener_inexistente_lanza_distribuidora_no_encontrada(db) -> None:
    with pytest.raises(service.DistribuidoraNoEncontrada):
        service.obtener_distribuidora(db, "no-existe")


def test_obtener_no_filtra_inactivas(db) -> None:
    creada = _distribuidora(db)
    service.desactivar_distribuidora(db, creada.id)

    assert service.obtener_distribuidora(db, creada.id).activo is False


# --- listar ---


def test_listar_pagina_activas_y_cuenta_el_total(db) -> None:
    for n in range(3):
        _distribuidora(db, nombre=f"D{n}")
    baja = _distribuidora(db, nombre="Baja")
    service.desactivar_distribuidora(db, baja.id)

    items, total = service.listar_distribuidoras(db, 1, 2)
    resto, _ = service.listar_distribuidoras(db, 2, 2)

    assert total == 3
    assert len(items) == 2
    assert len(resto) == 1


def test_listar_sin_distribuidoras_devuelve_vacio(db) -> None:
    assert service.listar_distribuidoras(db, 1, 20) == ([], 0)


# --- actualizar / desactivar ---


def test_actualizar_aplica_solo_campos_enviados(db) -> None:
    creada = _distribuidora(db, contacto="Juan")

    actualizada = service.actualizar_distribuidora(db, creada.id, DistribuidoraUpdate(nombre="Nueva"))

    assert actualizada.nombre == "Nueva"
    assert actualizada.contacto == "Juan"


def test_actualizar_inexistente_lanza_distribuidora_no_encontrada(db) -> None:
    with pytest.raises(service.DistribuidoraNoEncontrada):
        service.actualizar_distribuidora(db, "no-existe", DistribuidoraUpdate(nombre="X"))


def test_desactivar_hace_soft_delete(db) -> None:
    creada = _distribuidora(db)

    service.desactivar_distribuidora(db, creada.id)

    assert db.get(Distribuidora, creada.id).activo is False
    assert service.listar_distribuidoras(db, 1, 20)[1] == 0


def test_desactivar_inexistente_lanza_distribuidora_no_encontrada(db) -> None:
    with pytest.raises(service.DistribuidoraNoEncontrada):
        service.desactivar_distribuidora(db, "no-existe")


# --- lista de precios: agregar ---


def test_agregar_a_lista_persiste_la_entrada(db) -> None:
    distribuidora = _distribuidora(db)
    producto = _producto(db)

    entrada = _lista(db, distribuidora, producto, costo="800")

    assert entrada.id
    assert (entrada.distribuidora_id, entrada.producto_id) == (distribuidora.id, producto.id)
    assert entrada.costo == 800


def test_agregar_a_lista_con_distribuidora_inexistente(db) -> None:
    producto = _producto(db)

    with pytest.raises(service.DistribuidoraNoEncontrada):
        service.agregar_a_lista(
            db, "no-existe", ListaPrecioDistribuidoraCreate(producto_id=producto.id, costo=Decimal("1"))
        )


def test_agregar_a_lista_con_producto_inexistente(db) -> None:
    distribuidora = _distribuidora(db)

    with pytest.raises(service.ProductoNoEncontrado):
        service.agregar_a_lista(
            db, distribuidora.id, ListaPrecioDistribuidoraCreate(producto_id="no-existe", costo=Decimal("1"))
        )


def test_agregar_a_lista_producto_repetido_lanza_producto_ya_en_lista(db) -> None:
    distribuidora = _distribuidora(db)
    producto = _producto(db)
    _lista(db, distribuidora, producto)

    with pytest.raises(service.ProductoYaEnLista):
        _lista(db, distribuidora, producto, costo="900")

    assert db.query(ListaPrecio).count() == 1


def test_mismo_producto_en_otra_distribuidora_es_valido(db) -> None:
    producto = _producto(db)
    _lista(db, _distribuidora(db, nombre="A"), producto)
    _lista(db, _distribuidora(db, nombre="B"), producto)

    assert db.query(ListaPrecio).count() == 2


# --- lista de precios: listar / actualizar / quitar ---


def test_listar_lista_ordena_por_producto_id(db) -> None:
    distribuidora = _distribuidora(db)
    productos = [_producto(db, sku=f"S{n}") for n in range(3)]
    for producto in productos:
        _lista(db, distribuidora, producto)

    entradas = service.listar_lista(db, distribuidora.id)

    assert [e.producto_id for e in entradas] == sorted(p.id for p in productos)


def test_listar_lista_de_distribuidora_inexistente(db) -> None:
    with pytest.raises(service.DistribuidoraNoEncontrada):
        service.listar_lista(db, "no-existe")


def test_listar_lista_sin_entradas_devuelve_vacio(db) -> None:
    assert service.listar_lista(db, _distribuidora(db).id) == []


def test_actualizar_costo_lista_cambia_el_costo(db) -> None:
    distribuidora = _distribuidora(db)
    producto = _producto(db)
    _lista(db, distribuidora, producto, costo="800")

    entrada = service.actualizar_costo_lista(db, distribuidora.id, producto.id, ListaPrecioUpdate(costo=Decimal("950")))

    assert entrada.costo == 950


def test_actualizar_costo_lista_con_producto_fuera_de_la_lista(db) -> None:
    distribuidora = _distribuidora(db)

    with pytest.raises(service.EntradaNoEncontrada):
        service.actualizar_costo_lista(db, distribuidora.id, "no-existe", ListaPrecioUpdate(costo=Decimal("1")))


def test_actualizar_costo_lista_con_distribuidora_inexistente(db) -> None:
    with pytest.raises(service.DistribuidoraNoEncontrada):
        service.actualizar_costo_lista(db, "no-existe", "x", ListaPrecioUpdate(costo=Decimal("1")))


def test_quitar_de_lista_borra_la_fila_sin_tocar_producto_ni_distribuidora(db) -> None:
    distribuidora = _distribuidora(db)
    producto = _producto(db)
    _lista(db, distribuidora, producto)

    service.quitar_de_lista(db, distribuidora.id, producto.id)

    assert db.query(ListaPrecio).count() == 0
    assert db.get(Producto, producto.id) is not None
    assert db.get(Distribuidora, distribuidora.id) is not None


def test_quitar_de_lista_con_producto_fuera_de_la_lista(db) -> None:
    distribuidora = _distribuidora(db)

    with pytest.raises(service.EntradaNoEncontrada):
        service.quitar_de_lista(db, distribuidora.id, "no-existe")


def test_quitar_de_lista_con_distribuidora_inexistente(db) -> None:
    with pytest.raises(service.DistribuidoraNoEncontrada):
        service.quitar_de_lista(db, "no-existe", "x")


# --- comparar ---


def test_comparar_ordena_por_costo_y_calcula_precio_sugerido(db) -> None:
    producto = _producto(db, costo="1000", margen="0.5")
    cara = _distribuidora(db, nombre="Cara")
    barata = _distribuidora(db, nombre="Barata")
    _lista(db, cara, producto, costo="900")
    _lista(db, barata, producto, costo="600")

    filas = service.comparar_costos(db, producto.id)

    assert [f.distribuidora_nombre for f in filas] == ["Barata", "Cara"]
    assert [f.precio_sugerido for f in filas] == [Decimal("900"), Decimal("1350")]


def test_comparar_excluye_distribuidoras_inactivas(db) -> None:
    producto = _producto(db)
    activa = _distribuidora(db, nombre="Activa")
    baja = _distribuidora(db, nombre="Baja")
    _lista(db, activa, producto)
    _lista(db, baja, producto)
    service.desactivar_distribuidora(db, baja.id)

    filas = service.comparar_costos(db, producto.id)

    assert [f.distribuidora_nombre for f in filas] == ["Activa"]


def test_comparar_producto_sin_listas_devuelve_vacio(db) -> None:
    assert service.comparar_costos(db, _producto(db).id) == []


def test_comparar_producto_inexistente_lanza_producto_no_encontrado(db) -> None:
    with pytest.raises(service.ProductoNoEncontrado):
        service.comparar_costos(db, "no-existe")
