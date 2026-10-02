"""Fixtures compartidas C-03: app con SQLite + fakeredis via overrides.

Ninguna credencial real: usuarios seed con passwords `test-only-*`.
"""

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

DUENA_EMAIL = "duena@test.only"
DUENA_PASSWORD = "test-only-duena-password"
MOSTRADOR_EMAIL = "mostrador@test.only"
MOSTRADOR_PASSWORD = "test-only-mostrador-password"
INACTIVO_EMAIL = "inactivo@test.only"
INACTIVO_PASSWORD = "test-only-inactivo-password"


@pytest.fixture
def db_session_factory():
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


@pytest.fixture
def seed_users(db_session_factory):
    from app.core.security import hash_password
    from app.models import Usuario

    with db_session_factory() as session:
        session.add(
            Usuario(
                email=DUENA_EMAIL,
                password_hash=hash_password(DUENA_PASSWORD),
                rol="duena",
            )
        )
        session.add(
            Usuario(
                email=MOSTRADOR_EMAIL,
                password_hash=hash_password(MOSTRADOR_PASSWORD),
                rol="mostrador",
            )
        )
        session.add(
            Usuario(
                email=INACTIVO_EMAIL,
                password_hash=hash_password(INACTIVO_PASSWORD),
                rol="mostrador",
                activo=False,
            )
        )
        session.commit()
    return {
        "duena": (DUENA_EMAIL, DUENA_PASSWORD),
        "mostrador": (MOSTRADOR_EMAIL, MOSTRADOR_PASSWORD),
        "inactivo": (INACTIVO_EMAIL, INACTIVO_PASSWORD),
    }


@pytest.fixture
def fake_redis():
    import fakeredis

    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest_asyncio.fixture
async def client(db_session_factory, fake_redis, seed_users):
    from app import deps
    from app.main import create_app

    app = create_app()

    def _override_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = _override_db
    app.dependency_overrides[deps.get_redis] = lambda: fake_redis

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
