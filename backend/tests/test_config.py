import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_explicit_database_tls() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", database_url="postgresql+psycopg://u:p@db/app")


def test_sqlite_is_not_accepted_for_runtime() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", database_url="sqlite:///:memory:")


def test_remote_config_rejects_disabled_tls() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="staging",
            database_url="postgresql+psycopg://u:p@db.example/app?sslmode=disable",
        )


def test_error_hides_database_password() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://u:sensitive-value@localhost/app",
        )
    assert "sensitive-value" not in str(error.value)

