from fastapi import Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine


class HealthResponse(BaseModel):
    status: str


class ReadinessChecks(BaseModel):
    api: str
    database: str
    worker: str


class ReadinessResponse(BaseModel):
    status: str
    checks: ReadinessChecks


def check_database(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # No database error details or connection URL in HTTP response.
        return False


def health() -> HealthResponse:
    return HealthResponse(status="ok")


def readiness(engine: Engine, response: Response) -> ReadinessResponse:
    database_ready = check_database(engine)
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if database_ready else "not_ready",
        checks=ReadinessChecks(
            api="ready",
            database="ready" if database_ready else "unavailable",
            worker="not_configured",
        ),
    )
