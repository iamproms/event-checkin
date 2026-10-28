"""Brevo transport contracts without sending external email."""

import io
import json
from datetime import UTC, datetime
from urllib.error import HTTPError
from uuid import uuid4

from pydantic import SecretStr

import app.delivery.brevo as brevo_module
from app.api.webhooks import brevo_authorized
from app.delivery.brevo import BrevoTransactionalClient
from app.tickets.email import BrevoTicketTransport, ticket_message


class Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def read(self, _limit: int) -> bytes:
        return json.dumps(self.payload).encode()


def test_webhook_bearer_authentication_fails_closed() -> None:
    configured = SecretStr("synthetic-webhook-token")
    assert brevo_authorized(configured, "Bearer synthetic-webhook-token")
    assert not brevo_authorized(configured, "Bearer wrong")
    assert not brevo_authorized(configured, None)
    assert not brevo_authorized(None, "Bearer synthetic-webhook-token")


def test_ticket_transport_uses_intent_idempotency_and_tracking_headers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def send(request, timeout):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response({"messageId": "provider-message-1"})

    monkeypatch.setattr(brevo_module, "urlopen", send)
    tenant_id, intent_id = uuid4(), uuid4()
    message = ticket_message(
        tenant_id=tenant_id,
        intent_id=intent_id,
        recipient="synthetic@example.test",
        credential="v1." + "A" * 43,
        event_name="Reverb 5.0",
        starts_at=datetime(2026, 11, 1, 8, tzinfo=UTC),
        timezone="Africa/Lagos",
        organizer_name="Reverb",
        sender_name="Reverb Tickets",
    )
    provider_id = BrevoTicketTransport(
        BrevoTransactionalClient("synthetic-api-key"), "tickets@example.test"
    ).send(message)
    assert provider_id == "provider-message-1"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["headers"] == {
        "X-Mailin-custom": f"intent_id={intent_id}&tenant_id={tenant_id}",
        "idempotencyKey": str(intent_id),
    }
    assert body["to"] == [{"email": "synthetic@example.test"}]
    assert body["attachment"][0]["name"] == "event-ticket-qr.png"
    assert "cid:ticket-qr" not in body["htmlContent"]
    assert "attached as event-ticket-qr.png" in body["htmlContent"]
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"


def test_duplicate_idempotency_response_is_treated_as_already_processed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    key = str(uuid4())

    def duplicate(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise HTTPError(
            "https://api.brevo.com/v3/smtp/email",
            400,
            "duplicate",
            {},
            io.BytesIO(b'{"code":"duplicate_parameter"}'),
        )

    monkeypatch.setattr(brevo_module, "urlopen", duplicate)
    result = BrevoTransactionalClient("synthetic-api-key").send(
        {
            "sender": {"email": "tickets@example.test"},
            "to": [{"email": "synthetic@example.test"}],
            "subject": "Synthetic",
            "textContent": "Synthetic",
        },
        key,
    )
    assert result == f"brevo-idempotent-{key}"
