"""Authenticated provider callbacks that update durable delivery state."""

import hmac
from datetime import UTC, datetime
from typing import Annotated, cast
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.db.models import TicketDeliveryIntent
from app.db.session import authorized_tenant_session

router = APIRouter(prefix="/api/v1/webhooks", tags=["provider webhooks"])


def brevo_authorized(configured: object, authorization: str | None) -> bool:
    """Authenticate the callback before FastAPI parses an untrusted body."""
    token = getattr(configured, "get_secret_value", lambda: "")()
    expected = f"Bearer {token}" if token else ""
    return bool(authorization and expected and hmac.compare_digest(authorization, expected))


class BrevoEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event: str = Field(min_length=1, max_length=40)
    message_id: str = Field(
        min_length=1,
        max_length=500,
        validation_alias=AliasChoices("message-id", "messageId"),
    )
    custom: str = Field(
        min_length=1,
        max_length=500,
        validation_alias=AliasChoices("X-Mailin-custom", "x-mailin-custom"),
    )


def _credentials(custom: str) -> tuple[UUID, UUID]:
    try:
        values = parse_qs(custom, strict_parsing=True)
        intent_id = UUID(values["intent_id"][0])
        tenant_id = UUID(values["tenant_id"][0])
    except (KeyError, IndexError, ValueError) as exc:
        raise HTTPException(422, detail={"code": "WEBHOOK_INVALID"}) from exc
    return intent_id, tenant_id


def _message_id(value: str) -> str:
    return value.strip().removeprefix("<").removesuffix(">")


@router.post("/brevo", status_code=204)
def brevo_webhook(
    body: BrevoEvent,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    settings = request.app.state.settings
    if not brevo_authorized(settings.brevo_webhook_token, authorization):
        raise HTTPException(401, detail={"code": "WEBHOOK_AUTH_INVALID"})
    intent_id, tenant_id = _credentials(body.custom)
    engine = cast(Engine, request.app.state.database_engine)
    normalized = body.event.replace("-", "_").lower()
    with authorized_tenant_session(engine, tenant_id) as db:
        intent = db.scalar(
            select(TicketDeliveryIntent)
            .where(
                TicketDeliveryIntent.tenant_id == tenant_id,
                TicketDeliveryIntent.id == intent_id,
            )
            .with_for_update()
        )
        if intent is None:
            # Acknowledge unknown or already-purged events without exposing state.
            return Response(status_code=204)
        message_id = _message_id(body.message_id)
        if intent.provider_message_id is None or intent.provider_message_id.startswith(
            "brevo-idempotent-"
        ):
            intent.provider_message_id = message_id
        elif not hmac.compare_digest(_message_id(intent.provider_message_id), message_id):
            raise HTTPException(409, detail={"code": "WEBHOOK_MESSAGE_MISMATCH"})
        now = datetime.now(UTC)
        if normalized == "delivered":
            intent.status = "delivered"
            intent.delivered_at = now
            intent.error_code = None
            intent.failed_at = None
        elif (
            normalized
            in {
                "hard_bounce",
                "hardbounce",
                "soft_bounce",
                "softbounce",
                "blocked",
                "spam",
                "invalid",
                "invalid_email",
            }
            and intent.status != "delivered"
        ):
            intent.status = "bounced"
            intent.error_code = "PROVIDER_BOUNCE"
            intent.failed_at = now
        elif normalized == "error" and intent.status != "delivered":
            intent.status = "failed"
            intent.error_code = "PROVIDER_ERROR"
            intent.failed_at = now
    return Response(status_code=204)
