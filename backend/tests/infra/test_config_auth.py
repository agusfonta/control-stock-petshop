"""Auth settings por env + guard fail-closed (C-03 task 1.2, RED-first).

SECRET_KEY demo en entorno no-dev/test aborta el arranque; las TTLs de
tokens salen de env con los defaults del design (access 15min, refresh 7d).
"""

import pytest
from pydantic import ValidationError


def test_settings_defaults_ttl_y_env() -> None:
    from app.core.config import Settings

    settings = Settings(_env_file=None, secret_key="test-only-ephemeral-key")
    assert settings.access_token_expire_minutes == 15
    assert settings.refresh_token_expire_days == 7
    assert settings.env in ("dev", "test")


def test_settings_ttl_configurable_por_env() -> None:
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        secret_key="test-only-ephemeral-key",
        access_token_expire_minutes=5,
        refresh_token_expire_days=1,
    )
    assert settings.access_token_expire_minutes == 5
    assert settings.refresh_token_expire_days == 1


def test_arranca_con_demo_en_prod_aborta() -> None:
    """Fail-closed: SECRET_KEY demo + ENV=prod rechaza la config."""
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key="changeme", env="prod")


def test_secret_corta_en_prod_aborta() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key="corta", env="prod")


def test_demo_permitida_solo_en_dev_y_test() -> None:
    from app.core.config import Settings

    assert Settings(_env_file=None, secret_key="changeme", env="dev").env == "dev"
    assert Settings(_env_file=None, secret_key="changeme", env="test").env == "test"


@pytest.mark.parametrize("faltante", ["ENV", "SECRET_KEY", "DATABASE_URL"])
def test_variables_criticas_sin_default_son_obligatorias(
    monkeypatch: pytest.MonkeyPatch, faltante: str
) -> None:
    """ENV, SECRET_KEY y DATABASE_URL no tienen default: falta -> no arranca."""
    from app.core.config import Settings

    for nombre in ("ENV", "SECRET_KEY", "DATABASE_URL"):
        monkeypatch.setenv(nombre, "dev" if nombre == "ENV" else "valor-de-prueba-largo-123456789012")
    monkeypatch.delenv(faltante)

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    assert faltante.lower() in str(exc.value).lower()


def test_variables_criticas_presentes_arrancan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("SECRET_KEY", "test-only-ephemeral-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    settings = Settings(_env_file=None)
    assert (settings.env, settings.database_url) == ("dev", "sqlite:///:memory:")


STAGING_SECRET = "test-only-ephemeral-staging-secret-0123456789abcdef"
REDIS_REAL = "redis://redis:6379/0"


def test_staging_con_config_real_arranca() -> None:
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        env="staging",
        secret_key=STAGING_SECRET,
        redis_url=REDIS_REAL,
        bcrypt_rounds=12,
    )
    assert settings.env == "staging"


@pytest.mark.parametrize("secreto", ["changeme", "corta"])
def test_staging_con_secreto_demo_o_corto_aborta(secreto: str) -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, env="staging", secret_key=secreto, redis_url=REDIS_REAL
        )


def test_staging_con_redis_en_memoria_aborta() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            env="staging",
            secret_key=STAGING_SECRET,
            redis_url="memory://",
        )
    assert "redis" in str(exc.value).lower()


def test_staging_con_bcrypt_bajo_aborta() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            env="staging",
            secret_key=STAGING_SECRET,
            redis_url=REDIS_REAL,
            bcrypt_rounds=4,
        )


@pytest.mark.parametrize("valor", ["produccion", "Prod", "stagin"])
def test_env_desconocido_aborta_nombrando_los_validos(valor: str) -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, env=valor, secret_key=STAGING_SECRET)
    mensaje = str(exc.value)
    for valido in ("dev", "test", "staging", "prod"):
        assert valido in mensaje
