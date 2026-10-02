"""Generic repository + soft-delete (C-02 task 1.3, RED-first)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Producto
from app.repositories import Repository


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _producto(sku="SKU-REP-001") -> Producto:
    return Producto(
        sku=sku,
        nombre="Pipeta Gato",
        categoria="farmacia",
        unidad="unidad",
        costo=100,
        margen_pct=0.5,
        stock_actual=4,
        stock_minimo=1,
    )


def test_get_by_id_devuelve_entidad() -> None:
    session = _session()
    repo = Repository(session, Producto)
    producto = _producto()
    session.add(producto)
    session.commit()
    assert repo.get_by_id(producto.id) is not None
    assert repo.get_by_id(producto.id).sku == "SKU-REP-001"
    assert repo.get_by_id("inexistente") is None


def test_list_active_excluye_borrado_logico() -> None:
    session = _session()
    repo = Repository(session, Producto)
    session.add(_producto(sku="SKU-ACTIVO"))
    borrado = _producto(sku="SKU-BORRADO")
    session.add(borrado)
    session.commit()
    repo.soft_delete(borrado)
    session.commit()
    skus = [p.sku for p in repo.list_active()]
    assert "SKU-ACTIVO" in skus
    assert "SKU-BORRADO" not in skus


def test_soft_delete_conserva_la_fila_con_activo_false() -> None:
    session = _session()
    repo = Repository(session, Producto)
    producto = _producto()
    session.add(producto)
    session.commit()
    entity_id = producto.id
    repo.soft_delete(producto)
    session.commit()
    session.expire_all()
    conservada = repo.get_by_id(entity_id)
    assert conservada is not None
    assert conservada.activo is False
