"""Minimal Brevo transactional-email API client with provider idempotency."""

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.auth.email import DeliveryUnavailable


class BrevoTransactionalClient:
    def __init__(self, api_key: str, endpoint: str = "https://api.brevo.com/v3/smtp/email") -> None:
        if not api_key or not endpoint.startswith("https://"):
            raise ValueError("Brevo configuration is invalid")
        self.api_key = api_key
        self.endpoint = endpoint

    def send(self, payload: dict[str, Any], idempotency_key: str) -> str:
        headers = dict(payload.get("headers") or {})
        headers["idempotencyKey"] = idempotency_key
        payload = {**payload, "headers": headers}
        request = Request(
            self.endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": self.api_key,
                "user-agent": "event-checkin-platform/1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS endpoint
                result = json.loads(response.read(64 * 1024))
        except HTTPError as exc:
            try:
                error = json.loads(exc.read(16 * 1024))
            except (json.JSONDecodeError, UnicodeDecodeError):
                error = {}
            if error.get("code") == "duplicate_parameter":
                return f"brevo-idempotent-{idempotency_key}"
            raise DeliveryUnavailable("Transactional email provider rejected the request") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise DeliveryUnavailable("Transactional email provider is unavailable") from exc
        message_id = result.get("messageId")
        if not isinstance(message_id, str) or not 1 <= len(message_id) <= 500:
            raise DeliveryUnavailable("Transactional email provider returned an invalid response")
        return message_id.strip().removeprefix("<").removesuffix(">")
