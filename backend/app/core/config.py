"""Application settings loaded from environment (env-only secrets)."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All secrets come from env, never hardcoded."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "0.1.0"
    database_url: str = "postgresql://petshop:petshop@localhost:5432/petshop"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "changeme"
    env: str = "dev"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    @model_validator(mode="after")
    def _fail_closed_demo_secret(self) -> "Settings":
        """Abort startup with a demo/short SECRET_KEY outside dev/test."""
        if self.env in ("dev", "test"):
            return self
        if self.secret_key == "changeme" or len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY must be a real secret (>= 32 chars, not 'changeme') "
                f"when ENV={self.env!r}; refusing to start (fail-closed)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
