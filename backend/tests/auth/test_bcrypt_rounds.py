"""Costo de bcrypt configurable (BCRYPT_ROUNDS), fail-closed fuera de dev/test.

La suite baja el costo a 4 rounds (conftest) para no pagar ~250 ms por hash;
en produccion el piso es 12 y una config mas laxa aborta el arranque.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import hash_password, verify_password

SECRET_REAL = "s" * 40


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_default_es_12_rounds(monkeypatch):
    monkeypatch.delenv("BCRYPT_ROUNDS", raising=False)
    assert _settings().bcrypt_rounds == 12


@pytest.mark.parametrize("rounds", [4, 6])
def test_dev_y_test_admiten_rounds_bajos(rounds):
    assert _settings(env="test", bcrypt_rounds=rounds).bcrypt_rounds == rounds
    assert _settings(env="dev", bcrypt_rounds=rounds).bcrypt_rounds == rounds


@pytest.mark.parametrize("rounds", [4, 11])
def test_prod_rechaza_rounds_menores_a_12(rounds):
    with pytest.raises(ValidationError, match="BCRYPT_ROUNDS"):
        _settings(env="prod", secret_key=SECRET_REAL, bcrypt_rounds=rounds)


@pytest.mark.parametrize("rounds", [12, 14])
def test_prod_admite_12_o_mas(rounds):
    s = _settings(env="prod", secret_key=SECRET_REAL, bcrypt_rounds=rounds)
    assert s.bcrypt_rounds == rounds


@pytest.mark.parametrize("rounds", [3, 32])
def test_rounds_fuera_del_rango_de_bcrypt_se_rechaza(rounds):
    with pytest.raises(ValidationError):
        _settings(env="test", bcrypt_rounds=rounds)


def test_hash_password_usa_los_rounds_configurados_en_la_suite():
    hashed = hash_password("test-only-rounds")
    assert hashed.startswith("$2b$04$")
    assert verify_password("test-only-rounds", hashed)
    assert not verify_password("otro-password", hashed)
