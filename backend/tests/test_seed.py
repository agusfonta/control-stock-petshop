"""Seed idempotency + no-hardcoded-secrets (C-02 tasks 3.1/3.2, RED-first)."""

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Usuario
from scripts.seed import run_seed

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def test_seed_doble_ejecucion_no_duplica() -> None:
    factory = _factory()
    first = run_seed(session_factory=factory, owner_password="test-only")
    second = run_seed(session_factory=factory, owner_password="test-only")
    with factory() as session:
        assert session.query(Usuario).count() == 1
    assert first["owner_created"] is True
    assert second["owner_created"] is False


def test_seed_segunda_ejecucion_no_pisa_password() -> None:
    factory = _factory()
    run_seed(session_factory=factory, owner_password="test-only")
    with factory() as session:
        original = session.query(Usuario).one().password_hash
    run_seed(session_factory=factory, owner_password="otro-valor")
    with factory() as session:
        assert session.query(Usuario).one().password_hash == original


def test_seed_sin_password_falla_con_mensaje_claro() -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_seed(session_factory=_factory(), owner_password=None)
    assert "SEED_OWNER_PASSWORD" in str(excinfo.value.code)


def test_seed_sin_credenciales_reales_en_repo() -> None:
    text = (BACKEND_DIR / "scripts" / "seed.py").read_text(encoding="utf-8")
    assert "SEED_OWNER_PASSWORD" in text
    assert (
        re.search(r"password\s*=\s*['\"][^'\"]+['\"]", text, re.IGNORECASE)
        is None
    )
