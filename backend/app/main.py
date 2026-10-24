from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.api.auth import router as auth_router
from app.api.domains import router as domains_router
from app.api.events import router as events_router
from app.api.health import ReadinessResponse, health, readiness
from app.api.platform import router as platform_router
from app.auth.corpus import CompromisedPasswordCorpus
from app.auth.email import DisabledEmailDelivery, SmtpEmailDelivery
from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.engine import build_engine
from app.events.service import EventService
from app.tenancy.authority import AuthorityDenied, canonical_authority
from app.tenancy.domains import DisabledDomainProvider, DomainService, FixtureDomainProvider
from app.tenancy.platform_auth import PlatformAuth


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    database_engine = engine or build_engine(settings)
    identity_engine = (
        create_engine(settings.identity_database_url.get_secret_value(), pool_pre_ping=True)
        if settings.identity_database_url
        else None
    )
    platform_engine = (
        create_engine(settings.platform_database_url.get_secret_value(), pool_pre_ping=True)
        if settings.platform_database_url
        else None
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database_engine.dispose()
        if identity_engine is not None:
            identity_engine.dispose()
        if platform_engine is not None:
            platform_engine.dispose()

    app = FastAPI(title="Event Check-in API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def trusted_authority(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith("/api/"):
            try:
                host, origin = canonical_authority(request, settings)
            except AuthorityDenied:
                return JSONResponse(
                    status_code=421,
                    content={
                        "detail": {"code": "UNRECOGNIZED_HOST", "message": "Host is unavailable"}
                    },
                )
            request.state.trusted_hostname = host
            request.state.trusted_origin = origin
        return await call_next(request)

    @app.middleware("http")
    async def auth_cache_control(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(
            ("/api/v1/auth", "/api/v1/platform", "/api/v1/domains", "/api/v1/events")
        ):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.include_router(auth_router)
    app.include_router(platform_router)
    app.include_router(domains_router)
    app.include_router(events_router)
    app.state.auth_service = None
    app.state.platform_auth = None
    app.state.domain_service = None
    app.state.event_service = None
    app.state.email_delivery = DisabledEmailDelivery()
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
        app.state.email_delivery = email
        app.state.event_service = EventService(database_engine, app.state.auth_service)
    if platform_engine is not None and identity_engine is not None:
        app.state.platform_auth = PlatformAuth(identity_engine, settings)
        if settings.fallback_domain_suffix is not None:
            provider = (
                FixtureDomainProvider(settings.local_domain_fixture)
                if settings.local_domain_fixture and settings.app_env.value in {"local", "test"}
                else DisabledDomainProvider()
            )
            app.state.domain_service = DomainService(
                platform_engine,
                database_engine,
                app.state.auth_service,
                provider,
                settings.fallback_domain_suffix,
            )
    app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)

    def readiness_route(response: Response) -> ReadinessResponse:
        return readiness(database_engine, response)

    app.add_api_route("/ready", readiness_route, methods=["GET"], include_in_schema=False)
    return app


app = create_app()
