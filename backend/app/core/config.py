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
    identity_database_url: SecretStr | None = None
    auth_encryption_key: SecretStr | None = None
    auth_key_id: str = "v1"
    compromised_password_corpus: str | None = None
    compromised_password_sha256: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: int = 1025
    email_from: str | None = None
    log_level: str = "INFO"

    @field_validator("database_url", "identity_database_url")
    @classmethod
    def require_postgres(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
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
        if self.identity_database_url is not None:
            identity = make_url(self.identity_database_url.get_secret_value())
            runtime = make_url(self.database_url.get_secret_value())
            if identity.username == runtime.username:
                raise ValueError("identity and tenant runtime database roles must differ")
        if self.app_env in {Environment.STAGING, Environment.PRODUCTION}:
            if self.identity_database_url is not None and self.auth_encryption_key is None:
                raise ValueError("remote authentication requires AUTH_ENCRYPTION_KEY")
            for value in (self.database_url, self.identity_database_url):
                if value is None:
                    continue
                parsed = make_url(value.get_secret_value())
                if (
                    not parsed.password
                    or parsed.password == "REPLACE_ME"
                    or parsed.host == "DB_HOST"
                ):
                    raise ValueError("remote database URL contains an unset credential or host")
                if parsed.host in {"localhost", "127.0.0.1", "::1"}:
                    raise ValueError("remote environments cannot use a loopback database")
                if parsed.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
                    raise ValueError("remote database URL requires a TLS enforcing sslmode")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
