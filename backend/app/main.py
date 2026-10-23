from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from sqlalchemy.engine import Engine

from app.api.health import ReadinessResponse, health, readiness
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.engine import build_engine


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    database_engine = engine or build_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database_engine.dispose()

    app = FastAPI(title="Event Check-in API", version="0.1.0", lifespan=lifespan)
    app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)

    def readiness_route(response: Response) -> ReadinessResponse:
        return readiness(database_engine, response)

    app.add_api_route("/ready", readiness_route, methods=["GET"], include_in_schema=False)
    return app


app = create_app()

