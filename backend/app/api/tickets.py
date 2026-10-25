"""M3-02 administrative ticket status and audited lifecycle commands."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.auth import SESSION_COOKIE, csrf
from app.auth.service import AuthDenied, Forbidden
from app.tickets.service import TicketDenied, TicketService

router = APIRouter(
    prefix="/api/v1/events/{event_id}/registrations/{registration_id}/ticket", tags=["tickets"]
)


def service(request: Request) -> TicketService:
    result = getattr(request.app.state, "ticket_service", None)
    if result is None:
        raise HTTPException(
            503, detail={"code": "TICKETS_UNAVAILABLE", "message": "Ticket service unavailable"}
        )
    return cast(TicketService, result)


Service = Annotated[TicketService, Depends(service)]


def credentials(request: Request) -> tuple[str, str]:
    return request.state.trusted_hostname, request.cookies.get(SESSION_COOKIE, "")


def denied(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthDenied):
        return HTTPException(401, detail={"code": "AUTH_DENIED", "message": "Sign in required"})
    if isinstance(exc, Forbidden):
        return HTTPException(403, detail={"code": "FORBIDDEN", "message": "Access denied"})
    return HTTPException(409, detail={"code": "TICKET_STATE", "message": str(exc)})


@router.get("")
def status(
    event_id: UUID, registration_id: UUID, request: Request, tickets: Service
) -> dict[str, object]:
    try:
        return tickets.status(*credentials(request), event_id, registration_id)
    except (AuthDenied, Forbidden, TicketDenied) as exc:
        raise denied(exc) from exc


@router.post("/{action}", dependencies=[Depends(csrf)])
def command(
    event_id: UUID,
    registration_id: UUID,
    action: str,
    request: Request,
    tickets: Service,
) -> dict[str, object]:
    if action not in {"resend", "reissue", "revoke"}:
        raise HTTPException(404)
    try:
        return tickets.command(*credentials(request), event_id, registration_id, action)
    except (AuthDenied, Forbidden, TicketDenied) as exc:
        raise denied(exc) from exc
