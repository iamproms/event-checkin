import os

import pytest
from fastapi.testclient import TestClient

from app.api.auth import CHALLENGE_COOKIE, SESSION_COOKIE
from app.core.config import Settings

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_SYNC_ASGI_TESTS") == "1",
    reason="Local sandbox cannot schedule Starlette's sync endpoint threadpool",
)


@pytest.fixture
def app_factory(monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://runtime:local@localhost:5432/test")
    from app.main import create_app

    return create_app


def test_auth_csrf_cookie_and_fail_closed_without_identity_role(app_factory: object) -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://runtime:local@localhost:5432/test",
    )
    with TestClient(app_factory(settings=settings), base_url="https://testserver") as client:  # type: ignore[operator]
        no_csrf = client.post(
            "/api/v1/auth/login",
            json={"email": "staff@example.test", "password": "a password"},
        )
        assert no_csrf.status_code == 403
        assert no_csrf.headers["cache-control"] == "no-store"
        token = client.get("/api/v1/auth/csrf")
        assert token.status_code == 200
        cookie = token.headers["set-cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
        unavailable = client.post(
            "/api/v1/auth/login",
            json={"email": "staff@example.test", "password": "a password"},
            headers={"x-csrf-token": token.json()["csrf_token"]},
        )
        assert unavailable.status_code == 503


def test_cross_origin_mutation_rejected(app_factory: object) -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://runtime:local@localhost:5432/test",
    )
    with TestClient(app_factory(settings=settings), base_url="https://testserver") as client:  # type: ignore[operator]
        token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/v1/auth/logout", headers={"x-csrf-token": token, "origin": "https://evil.test"}
        )
        assert response.status_code == 403


def test_successful_login_revokes_previous_session_and_challenge(app_factory: object) -> None:
    class RecordingAuth:
        def __init__(self) -> None:
            self.revoked: list[str] = []
            self.cancelled: list[str] = []

        def login(self, hostname: str, email: str, password: str, ip: str) -> tuple[str, str]:
            assert hostname == "testserver"
            return "session", "new-session"

        def logout(self, token: str) -> None:
            self.revoked.append(token)

        def cancel_challenge(self, token: str) -> None:
            self.cancelled.append(token)

    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://runtime:local@localhost:5432/test",
    )
    app = app_factory(settings=settings)  # type: ignore[operator]
    auth = RecordingAuth()
    app.state.auth_service = auth
    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        client.cookies.set(SESSION_COOKIE, "previous-session")
        client.cookies.set(CHALLENGE_COOKIE, "previous-challenge")
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "staff@example.test", "password": "example password"},
            headers={"x-csrf-token": csrf},
        )
        assert response.status_code == 200
        assert auth.revoked == ["previous-session"]
        assert auth.cancelled == ["previous-challenge"]
        assert any("new-session" in cookie for cookie in response.headers.get_list("set-cookie"))
