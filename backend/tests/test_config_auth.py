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
