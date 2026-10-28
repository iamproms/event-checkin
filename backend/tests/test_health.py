from fastapi import Response
from sqlalchemy import create_engine, event

from app.api.health import health, readiness


def test_health_does_not_require_database() -> None:
    assert health().model_dump() == {"status": "ok"}


def test_readiness_reports_database_failure() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "engine_connect")
    def fail_connect(*_: object) -> None:
        raise OSError("simulated database outage")

    response = Response()
    result = readiness(engine, response)
    assert response.status_code == 503
    assert result.model_dump() == {
        "status": "not_ready",
        "checks": {"api": "ready", "database": "unavailable", "worker": "not_configured"},
    }


def test_readiness_reports_database_success() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    response = Response()
    result = readiness(engine, response)
    assert response.status_code == 200
    assert result.model_dump()["checks"] == {
        "api": "ready",
        "database": "ready",
        "worker": "not_configured",
    }
