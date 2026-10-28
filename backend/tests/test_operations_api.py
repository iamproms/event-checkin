"""FastAPI contract checks for authoritative gate redemption results."""

import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.api.auth import CSRF_COOKIE, SESSION_COOKIE
from app.api.operations import gate_router
from app.auth.service import AuthDenied

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_SYNC_ASGI_TESTS") == "1",
    reason="Local sandbox cannot schedule Starlette's sync endpoint threadpool",
)

EVENT = uuid4()
GATE = uuid4()


class FakeOperations:
    reason_code = "INVALID_TICKET"
    outcome = "invalid"

    def redeem(
        self, host: str, token: str, event_id: UUID, gate_id: UUID, credential: str
    ) -> dict[str, object]:
        if token != "scanner-session":
            raise AuthDenied("scanner session required")
        assert host == "gate.example.test"
        assert (event_id, gate_id, credential) == (EVENT, GATE, "x" * 20)
        return {
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "confirmed_at": datetime(2026, 10, 28, 9, 0, tzinfo=UTC),
            "participant_email": "must-not-serialize@example.test",
        }


@pytest.fixture
def gate_client() -> TestClient:
    app = FastAPI()
    app.state.event_operations_service = FakeOperations()

    @app.middleware("http")
    async def trusted_authority(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.trusted_hostname = "gate.example.test"
        request.state.trusted_origin = "https://gate.example.test"
        return await call_next(request)

    app.include_router(gate_router)
    return TestClient(app, base_url="https://gate.example.test")


@pytest.mark.parametrize(
    ("reason_code", "outcome"),
    [
        ("ACCEPTED", "accepted"),
        ("DUPLICATE_ADMISSION", "duplicate"),
        ("REVOKED_TICKET", "revoked"),
        ("INVALID_TICKET", "invalid"),
        ("EVENT_UNAVAILABLE", "invalid"),
        ("GATE_UNAVAILABLE", "invalid"),
        ("CHECKIN_NOT_OPEN", "invalid"),
        ("CHECKIN_CLOSED", "invalid"),
        ("CHECKIN_WINDOW_UNAVAILABLE", "invalid"),
    ],
)
def test_redeem_serializes_every_stable_reason(
    gate_client: TestClient, reason_code: str, outcome: str
) -> None:
    service = gate_client.app.state.event_operations_service
    service.reason_code, service.outcome = reason_code, outcome
    gate_client.cookies.set(SESSION_COOKIE, "scanner-session")
    gate_client.cookies.set(CSRF_COOKIE, "csrf-token")
    response = gate_client.post(
        "/api/v1/gate/redeem",
        headers={
            "x-csrf-token": "csrf-token",
            "origin": "https://gate.example.test",
        },
        json={"event_id": str(EVENT), "gate_id": str(GATE), "credential": "x" * 20},
    )
    assert response.status_code == 200
    assert response.json() == {
        "outcome": outcome,
        "reason_code": reason_code,
        "confirmed_at": "2026-10-28T09:00:00Z",
    }


def test_redeem_requires_cookie_and_csrf(gate_client: TestClient) -> None:
    body = {"event_id": str(EVENT), "gate_id": str(GATE), "credential": "x" * 20}
    no_csrf = gate_client.post("/api/v1/gate/redeem", json=body)
    assert no_csrf.status_code == 403
    gate_client.cookies.set(CSRF_COOKIE, "csrf-token")
    no_session = gate_client.post(
        "/api/v1/gate/redeem",
        headers={"x-csrf-token": "csrf-token"},
        json=body,
    )
    assert no_session.status_code == 401
