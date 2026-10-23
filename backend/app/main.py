from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.api.auth import router as auth_router
from app.api.health import ReadinessResponse, health, readiness
from app.auth.corpus import CompromisedPasswordCorpus
from app.auth.email import DisabledEmailDelivery, SmtpEmailDelivery
from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.engine import build_engine


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    database_engine = engine or build_engine(settings)
    identity_engine = (
        create_engine(settings.identity_database_url.get_secret_value(), pool_pre_ping=True)
        if settings.identity_database_url
        else None
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database_engine.dispose()
        if identity_engine is not None:
            identity_engine.dispose()

    app = FastAPI(title="Event Check-in API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def auth_cache_control(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/auth"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.include_router(auth_router)
    app.state.auth_service = None
    if identity_engine is not None:
        email = (
            SmtpEmailDelivery(
                settings.email_smtp_host, settings.email_smtp_port, settings.email_from
            )
            if settings.app_env.value in {"local", "test"}
            and settings.email_smtp_host
            and settings.email_from
            else DisabledEmailDelivery()
        )
        app.state.auth_service = AuthService(
            identity_engine,
            settings,
            CompromisedPasswordCorpus(
                settings.compromised_password_corpus, settings.compromised_password_sha256
            ),
            email,
        )
    app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)

    def readiness_route(response: Response) -> ReadinessResponse:
        return readiness(database_engine, response)

    app.add_api_route("/ready", readiness_route, methods=["GET"], include_in_schema=False)
    return app


app = create_app()
