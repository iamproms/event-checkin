from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    app_env: Environment
    database_url: SecretStr
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        value = value.upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")
        return value

    @model_validator(mode="after")
    def enforce_nonlocal_transport(self) -> "Settings":
        if self.app_env in {Environment.STAGING, Environment.PRODUCTION}:
            parsed = make_url(self.database_url.get_secret_value())
            if not parsed.password or parsed.password == "REPLACE_ME" or parsed.host == "DB_HOST":
                raise ValueError("remote DATABASE_URL contains an unset credential or host")
            if parsed.host in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("remote environments cannot use a loopback database")
            if parsed.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("remote DATABASE_URL requires a TLS enforcing sslmode")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

