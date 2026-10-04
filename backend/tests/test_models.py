"""Domain model constraints + RN-PR-01 (C-02, RED-first).

SQLite for CHECK/UNIQUE + price formula. Migration/trgm tests are pg_only
elsewhere. Every test below MUST fail on RED (models do not exist yet).
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Cliente,
    Distribuidora,
    ListaPrecio,
    Producto,
    Usuario,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as value:
        yield value


def _usuario(email="duena@petshop.local"):
    return Usuario(email=email, password_hash="hash-seed-only", rol="duena")


def _producto(sku="SKU-001", stock_actual=10):
    return Producto(
        sku=sku,
        nombre="Alimento Perro 20kg",
        marca="Marca",
        categoria="alimentos",
        unidad="bolsa",
        costo=Decimal("1000"),
        margen_pct=Decimal("0.5"),
        stock_actual=stock_actual,
        stock_minimo=2,
    )


def test_producto_stock_negativo_rechazado(session) -> None:
    session.add(_producto(stock_actual=-1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_producto_stock_negativo_en_update_no_cambia_almacenado(session) -> None:
    producto = _producto(stock_actual=5)
    session.add(producto)
    session.commit()
    producto.stock_actual = -3
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    session.refresh(producto)
    assert producto.stock_actual == 5


def test_producto_sku_duplicado_rechazado(session) -> None:
    session.add(_producto(sku="SKU-DUP"))
    session.commit()
    session.add(_producto(sku="SKU-DUP"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_usuario_email_duplicado_rechazado(session) -> None:
    session.add(_usuario(email="dup@petshop.local"))
    session.commit()
    session.add(_usuario(email="dup@petshop.local"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_precio_venta_es_costo_por_uno_mas_margen(session) -> None:
    producto = _producto()
    session.add(producto)
    session.commit()
    session.refresh(producto)
    assert producto.precio_venta == Decimal("1500")


def test_precio_venta_triangulador_segundo_caso(session) -> None:
    producto = _producto(sku="SKU-200")
    producto.costo = Decimal("200")
    producto.margen_pct = Decimal("0.25")
    session.add(producto)
    session.commit()
    session.refresh(producto)
    assert producto.precio_venta == Decimal("250")


def test_precio_se_actualiza_al_cambiar_costo(session) -> None:
    producto = _producto()
    session.add(producto)
    session.commit()
    session.refresh(producto)
    antes = producto.precio_venta
    producto.costo = Decimal("2000")
    session.commit()
    session.refresh(producto)
    assert producto.precio_venta > antes
    assert producto.precio_venta == Decimal("3000")


def test_usuario_nuevo_activo_por_defecto_con_auditoria(session) -> None:
    usuario = _usuario()
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    assert usuario.activo is True
    assert usuario.created_at is not None
    assert usuario.updated_at is not None


def test_cliente_saldo_cc_default_cero(session) -> None:
    cliente = Cliente(nombre="Juan Perez")
    session.add(cliente)
    session.commit()
    session.refresh(cliente)
    assert cliente.saldo_cc == 0
    assert cliente.activo is True


def test_producto_sin_distribuidora_persiste_con_fk_nula(session) -> None:
    producto = _producto()
    session.add(producto)
    session.commit()
    session.refresh(producto)
    assert producto.distribuidora_default_id is None
    assert producto.id is not None


def test_producto_con_distribuidora_referencia_opcional(session) -> None:
    distribuidora = Distribuidora(nombre="Distri Sur")
    session.add(distribuidora)
    session.flush()
    producto = _producto(sku="SKU-DIST")
    producto.distribuidora_default_id = distribuidora.id
    session.add(producto)
    session.commit()
    assert producto.distribuidora_default_id == distribuidora.id


# --- C-04: ListaPrecio (costos por distribuidora) ---


def test_lista_precio_se_crea_y_lee_con_relaciones(session) -> None:
    distribuidora = Distribuidora(nombre="Distri Sur")
    session.add(distribuidora)
    session.flush()
    producto = _producto(sku="SKU-LISTA")
    session.add(producto)
    session.flush()
    lista = ListaPrecio(
        distribuidora_id=distribuidora.id,
        producto_id=producto.id,
        costo=Decimal("800"),
    )
    session.add(lista)
    session.commit()
    session.refresh(lista)
    assert lista.id is not None
    assert lista.costo == Decimal("800")
    assert lista.distribuidora_id == distribuidora.id
    assert lista.producto_id == producto.id
    assert lista.activo is True


def test_lista_precio_par_distribuidora_producto_unico(session) -> None:
    distribuidora = Distribuidora(nombre="Distri Sur")
    session.add(distribuidora)
    session.flush()
    producto = _producto(sku="SKU-LISTA-UNO")
    session.add(producto)
    session.flush()
    session.add(
        ListaPrecio(
            distribuidora_id=distribuidora.id,
            producto_id=producto.id,
            costo=Decimal("800"),
        )
    )
    session.commit()
    session.add(
        ListaPrecio(
            distribuidora_id=distribuidora.id,
            producto_id=producto.id,
            costo=Decimal("900"),
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_lista_precio_relaciona_producto_y_distribuidora(session) -> None:
    distribuidora = Distribuidora(nombre="Distri Sur")
    session.add(distribuidora)
    session.flush()
    producto = _producto(sku="SKU-LISTA-REL")
    session.add(producto)
    session.flush()
    lista = ListaPrecio(
        distribuidora_id=distribuidora.id,
        producto_id=producto.id,
        costo=Decimal("800"),
    )
    session.add(lista)
    session.commit()
    session.refresh(lista)
    assert lista.producto.sku == "SKU-LISTA-REL"
    assert lista.distribuidora.nombre == "Distri Sur"
