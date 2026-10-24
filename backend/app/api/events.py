"""Tenant event configuration API; host and session establish authority."""

import re
from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError

from app.api.auth import SESSION_COOKIE, csrf
from app.auth.service import AuthDenied, Forbidden
from app.events.service import EventConflict, EventInvalid, EventService

router = APIRouter(prefix="/api/v1/events", tags=["event configuration"])
OFFSET_TIMESTAMP = re.compile(r"T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEvent(StrictBody):
    slug: str
    name: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    location: str | None = None

    @field_validator("starts_at", "ends_at", mode="before")
    @classmethod
    def offset_timestamp(cls, value: object) -> object:
        if not isinstance(value, str) or OFFSET_TIMESTAMP.search(value) is None:
            raise ValueError("Use an ISO 8601 timestamp with an explicit UTC offset")
        return value


class EditEvent(StrictBody):
    revision: int
    name: str
    location: str | None = None
    starts_at: datetime
    ends_at: datetime
    timezone: str
    registration_opens_at: datetime | None = None
    registration_closes_at: datetime | None = None
    checkin_opens_at: datetime | None = None
    checkin_closes_at: datetime | None = None

    @field_validator(
        "starts_at",
        "ends_at",
        "registration_opens_at",
        "registration_closes_at",
        "checkin_opens_at",
        "checkin_closes_at",
        mode="before",
    )
    @classmethod
    def offset_timestamp(cls, value: object) -> object:
        if value is None:
            return None
        return CreateEvent.offset_timestamp(value)


class FormBody(StrictBody):
    revision: int
    form_schema: dict[str, object]


class TransitionBody(StrictBody):
    revision: int


class GateBody(StrictBody):
    name: str
    enabled: bool = True


def service(request: Request) -> EventService:
    result = getattr(request.app.state, "event_service", None)
    if result is None:
        raise HTTPException(
            503, detail={"code": "EVENTS_UNAVAILABLE", "message": "Event management unavailable"}
        )
    return cast(EventService, result)


Service = Annotated[EventService, Depends(service)]


def credentials(request: Request) -> tuple[str, str]:
    return request.state.trusted_hostname, request.cookies.get(SESSION_COOKIE, "")


def denied(exc: Exception) -> HTTPException:
    if isinstance(exc, Forbidden):
        return HTTPException(403, detail={"code": "FORBIDDEN", "message": "Access denied"})
    if isinstance(exc, AuthDenied):
        return HTTPException(401, detail={"code": "AUTH_DENIED", "message": "Sign in required"})
    if isinstance(exc, (EventConflict, IntegrityError)):
        return HTTPException(
            409,
            detail={"code": "EVENT_CONFLICT", "message": "Configuration changed or already exists"},
        )
    return HTTPException(422, detail={"code": "EVENT_INVALID", "message": str(exc)})


def view(event: object) -> dict[str, object]:
    from app.db.models import Event

    row = cast(Event, event)
    return {
        "id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "status": row.status,
        "starts_at": row.starts_at.isoformat(),
        "ends_at": row.ends_at.isoformat(),
        "timezone": row.timezone,
        "location": row.location,
        "registration_opens_at": row.registration_opens_at.isoformat()
        if row.registration_opens_at
        else None,
        "registration_closes_at": row.registration_closes_at.isoformat()
        if row.registration_closes_at
        else None,
        "checkin_opens_at": row.checkin_opens_at.isoformat() if row.checkin_opens_at else None,
        "checkin_closes_at": row.checkin_closes_at.isoformat() if row.checkin_closes_at else None,
        "form_schema": row.form_schema,
        "form_schema_version": row.form_schema_version,
        "pii_purge_due_at": row.pii_purge_due_at.isoformat(),
        "revision": row.revision,
    }


def gate_view(gate: object) -> dict[str, object]:
    from app.db.models import Gate

    row = cast(Gate, gate)
    return {
        "id": str(row.id),
        "event_id": str(row.event_id),
        "name": row.name,
        "enabled": row.status == "active",
    }


@router.get("")
def list_events(request: Request, events: Service) -> dict[str, object]:
    try:
        return {"events": [view(row) for row in events.list_events(*credentials(request))]}
    except (AuthDenied, Forbidden) as exc:
        raise denied(exc) from exc


@router.post("", status_code=201, dependencies=[Depends(csrf)])
def create(body: CreateEvent, request: Request, events: Service) -> dict[str, object]:
    try:
        return view(events.create(*credentials(request), **body.model_dump()))
    except (AuthDenied, Forbidden, EventInvalid, EventConflict, IntegrityError) as exc:
        raise denied(exc) from exc


@router.get("/{event_id}")
def detail(event_id: UUID, request: Request, events: Service) -> dict[str, object]:
    try:
        return view(events.get(*credentials(request), event_id))
    except (AuthDenied, Forbidden, EventInvalid) as exc:
        raise denied(exc) from exc


@router.put("/{event_id}", dependencies=[Depends(csrf)])
def edit(event_id: UUID, body: EditEvent, request: Request, events: Service) -> dict[str, object]:
    try:
        data = body.model_dump()
        revision = data.pop("revision")
        return view(events.edit(*credentials(request), event_id, revision, **data))
    except (AuthDenied, Forbidden, EventInvalid, EventConflict, IntegrityError) as exc:
        raise denied(exc) from exc


@router.put("/{event_id}/form", dependencies=[Depends(csrf)])
def save_form(
    event_id: UUID, body: FormBody, request: Request, events: Service
) -> dict[str, object]:
    try:
        return view(
            events.set_form(*credentials(request), event_id, body.revision, body.form_schema)
        )
    except (AuthDenied, Forbidden, EventInvalid, EventConflict, IntegrityError) as exc:
        raise denied(exc) from exc


@router.get("/{event_id}/readiness")
def check_readiness(event_id: UUID, request: Request, events: Service) -> dict[str, object]:
    try:
        missing = events.inspect_readiness(*credentials(request), event_id)
        return {"ready": not missing, "instructions": missing}
    except (AuthDenied, Forbidden, EventInvalid) as exc:
        raise denied(exc) from exc


@router.post("/{event_id}/transitions/{action}", dependencies=[Depends(csrf)])
def transition(
    event_id: UUID, action: str, body: TransitionBody, request: Request, events: Service
) -> dict[str, object]:
    if action not in {"publish", "close", "cancel"}:
        raise HTTPException(404)
    target = {"publish": "published", "close": "closed", "cancel": "cancelled"}[action]
    try:
        return view(events.transition(*credentials(request), event_id, body.revision, target))
    except (AuthDenied, Forbidden, EventInvalid, EventConflict, IntegrityError) as exc:
        raise denied(exc) from exc


@router.get("/{event_id}/gates")
def list_gates(event_id: UUID, request: Request, events: Service) -> dict[str, object]:
    try:
        return {"gates": [gate_view(row) for row in events.gates(*credentials(request), event_id)]}
    except (AuthDenied, Forbidden, EventInvalid) as exc:
        raise denied(exc) from exc


@router.post("/{event_id}/gates", status_code=201, dependencies=[Depends(csrf)])
def create_gate(
    event_id: UUID, body: GateBody, request: Request, events: Service
) -> dict[str, object]:
    try:
        return gate_view(events.save_gate(*credentials(request), event_id, **body.model_dump()))
    except (AuthDenied, Forbidden, EventInvalid, EventConflict, IntegrityError) as exc:
        raise denied(exc) from exc


@router.put("/{event_id}/gates/{gate_id}", dependencies=[Depends(csrf)])
def edit_gate(
    event_id: UUID, gate_id: UUID, body: GateBody, request: Request, events: Service
) -> dict[str, object]:
    try:
        return gate_view(
            events.save_gate(*credentials(request), event_id, gate_id=gate_id, **body.model_dump())
        )
    except (AuthDenied, Forbidden, EventInvalid, EventConflict, IntegrityError) as exc:
        raise denied(exc) from exc
