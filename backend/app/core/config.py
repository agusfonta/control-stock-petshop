"""Application settings loaded from environment (env-only secrets)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All secrets come from env, never hardcoded."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "0.1.0"
    database_url: str = "postgresql://petshop:petshop@localhost:5432/petshop"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "changeme"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
