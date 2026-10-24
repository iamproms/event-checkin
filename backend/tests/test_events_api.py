"""Event route security contract without a database substitute."""

from collections.abc import Awaitable, Callable

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.events import CreateEvent, EditEvent, router
from app.auth.service import Forbidden


class DenyingService:
    def list_events(self, host: str, token: str) -> list[object]:
        raise Forbidden("No event permission")


def test_event_api_requires_explicit_offset_strings() -> None:
    data = {
        "slug": "test",
        "name": "Test",
        "timezone": "Africa/Lagos",
        "starts_at": "2026-11-01T09:00:00+01:00",
        "ends_at": "2026-11-01T10:00:00Z",
    }
    assert CreateEvent.model_validate(data).starts_at.utcoffset() is not None
    for invalid in ("2026-11-01T09:00:00", 1793520000):
        with pytest.raises(ValidationError):
            CreateEvent.model_validate({**data, "starts_at": invalid})
    with pytest.raises(ValidationError):
        EditEvent.model_validate({**data, "revision": 1, "checkin_opens_at": "2026-11-01T09:00"})


def test_permission_denial_is_403_and_mutation_needs_csrf() -> None:
    app = FastAPI()
    app.state.event_service = DenyingService()

    @app.middleware("http")
    async def trusted_host(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.trusted_hostname = "tenant.example.test"
        request.state.trusted_origin = "https://tenant.example.test"
        return await call_next(request)

    app.include_router(router)
    client = TestClient(app, base_url="https://tenant.example.test")
    denied = client.get("/api/v1/events")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "FORBIDDEN"
    without_csrf = client.post(
        "/api/v1/events",
        json={
            "slug": "test",
            "name": "Test",
            "starts_at": "2026-11-01T09:00:00+01:00",
            "ends_at": "2026-11-01T10:00:00+01:00",
            "timezone": "Africa/Lagos",
        },
    )
    assert without_csrf.status_code == 403
    assert without_csrf.json()["detail"]["code"] == "CSRF_INVALID"
