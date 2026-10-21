"""C-19 task 2.1: ClienteUpdate.mascotas (reemplazo) validado en el borde."""

import pytest
from pydantic import ValidationError

from app.modules.clientes.schemas import ClienteUpdate, MascotaEdicion


def test_ausente_no_se_marca_como_enviado() -> None:
    cambios = ClienteUpdate.model_validate({"nombre": "Ana"}).model_dump(exclude_unset=True)
    assert "mascotas" not in cambios


def test_lista_vacia_se_marca_como_enviada() -> None:
    cambios = ClienteUpdate.model_validate({"mascotas": []}).model_dump(exclude_unset=True)
    assert cambios["mascotas"] == []


def test_lista_mixta_con_y_sin_id_se_normaliza() -> None:
    data = ClienteUpdate.model_validate(
        {"mascotas": [{"id": "m1", "nombre": "  Rex ", "tipo": "perro"}, {"nombre": "Mishi", "tipo": "gato"}]}
    )
    assert data.mascotas is not None
    assert [(m.id, m.nombre, m.tipo) for m in data.mascotas] == [("m1", "Rex", "perro"), (None, "Mishi", "gato")]


def test_null_explicito_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        ClienteUpdate.model_validate({"mascotas": None})


@pytest.mark.parametrize(
    "mascota",
    [
        {"nombre": "", "tipo": "perro"},
        {"nombre": "   ", "tipo": "perro"},
        {"nombre": "x" * 101, "tipo": "perro"},
        {"nombre": "Rex", "tipo": "pez"},
        {"nombre": "Rex"},
        {"tipo": "perro"},
        {"nombre": "Rex", "tipo": "perro", "edad": 3},
        {"id": 5, "nombre": "Rex", "tipo": "perro"},
        {"id": "", "nombre": "Rex", "tipo": "perro"},
    ],
)
def test_mascota_invalida_se_rechaza(mascota) -> None:
    with pytest.raises(ValidationError):
        ClienteUpdate.model_validate({"mascotas": [mascota]})


def test_maximo_20_mascotas() -> None:
    def _lista(n: int) -> list[dict]:
        return [{"nombre": f"M{i}", "tipo": "gato"} for i in range(n)]

    assert len(ClienteUpdate.model_validate({"mascotas": _lista(20)}).mascotas or []) == 20
    with pytest.raises(ValidationError):
        ClienteUpdate.model_validate({"mascotas": _lista(21)})


def test_ids_repetidos_se_rechazan() -> None:
    with pytest.raises(ValidationError):
        ClienteUpdate.model_validate(
            {"mascotas": [{"id": "m1", "nombre": "A", "tipo": "gato"}, {"id": "m1", "nombre": "B", "tipo": "gato"}]}
        )


def test_varias_sin_id_no_cuentan_como_repetidas() -> None:
    data = ClienteUpdate.model_validate(
        {"mascotas": [{"nombre": "A", "tipo": "gato"}, {"nombre": "A", "tipo": "gato"}]}
    )
    assert data.mascotas is not None and len(data.mascotas) == 2


def test_mascota_edicion_es_estricta() -> None:
    with pytest.raises(ValidationError):
        MascotaEdicion.model_validate({"nombre": "Rex", "tipo": "perro", "activo": True})
