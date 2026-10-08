"""Application settings loaded from environment (env-only secrets)."""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All secrets come from env, never hardcoded."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://petshop:petshop@localhost:5432/petshop"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "changeme"
    env: str = "dev"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    # Zona del negocio para imputar ventas a un dia local en los reportes
    # (C-14 D5). Se valida al cargar: una zona mal escrita aborta el arranque.
    reportes_tz: str = "America/Argentina/Buenos_Aires"
    # Origenes admitidos por CORS, separados por comas (C-13 D14). Por defecto
    # el origen del servidor de desarrollo de Vite.
    cors_origins: str = "http://localhost:5173"
    # Costo de bcrypt (rounds). 12 es el piso en produccion; la suite de tests
    # lo baja a 4 (minimo de bcrypt) para no pagar ~250 ms por hash.
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)

    @property
    def cors_origins_list(self) -> list[str]:
        """Lista de origenes CORS ya recortada y sin vacios."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _memory_redis_solo_dev_test(self) -> "Settings":
        """`memory://` (Redis en memoria) solo se admite en dev/test (C-13 D14)."""
        if self.redis_url.startswith("memory://") and self.env not in ("dev", "test"):
            raise ValueError(
                "REDIS_URL=memory:// solo se admite con ENV=dev o ENV=test "
                f"(ENV={self.env!r}); usa un Redis real fuera de desarrollo."
            )
        return self

    @model_validator(mode="after")
    def _validar_reportes_tz(self) -> "Settings":
        """Rechaza un REPORTES_TZ que no sea una zona IANA conocida."""
        try:
            ZoneInfo(self.reportes_tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(
                f"REPORTES_TZ invalida: {self.reportes_tz!r} no es una zona IANA"
            ) from None
        return self

    @model_validator(mode="after")
    def _fail_closed_bcrypt_rounds(self) -> "Settings":
        """Fuera de dev/test, BCRYPT_ROUNDS debe ser >= 12 (fail-closed)."""
        if self.env not in ("dev", "test") and self.bcrypt_rounds < 12:
            raise ValueError(
                f"BCRYPT_ROUNDS={self.bcrypt_rounds} es demasiado bajo con "
                f"ENV={self.env!r}; el minimo fuera de dev/test es 12."
            )
        return self

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
