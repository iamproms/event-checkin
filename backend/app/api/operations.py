"""Event-critical participant import, attendance, export and gate APIs."""

from email.parser import BytesParser
from email.policy import default
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import SESSION_COOKIE, csrf
from app.auth.service import AuthDenied, Forbidden
from app.operations.service import EventOperationsService, OperationDenied

event_router = APIRouter(prefix="/api/v1/events/{event_id}", tags=["event operations"])
gate_router = APIRouter(prefix="/api/v1/gate", tags=["gate operations"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportPolicy(StrictBody):
    mapping: dict[str, object]
    notice_version: int = Field(ge=1)
    lawful_basis: str = Field(min_length=1, max_length=500)


class RedeemBody(StrictBody):
    event_id: UUID
    gate_id: UUID
    credential: str = Field(min_length=20, max_length=512)


def service(request: Request) -> EventOperationsService:
    result = getattr(request.app.state, "event_operations_service", None)
    if result is None:
        raise HTTPException(
            503,
            detail={"code": "EVENT_OPERATIONS_UNAVAILABLE", "message": "Operations unavailable"},
        )
    return cast(EventOperationsService, result)


Service = Annotated[EventOperationsService, Depends(service)]


def credentials(request: Request) -> tuple[str, str]:
    return request.state.trusted_hostname, request.cookies.get(SESSION_COOKIE, "")


def denied(exc: Exception) -> HTTPException:
    if isinstance(exc, Forbidden):
        return HTTPException(403, detail={"code": "FORBIDDEN", "message": "Access denied"})
    if isinstance(exc, AuthDenied):
        return HTTPException(401, detail={"code": "AUTH_DENIED", "message": "Sign in required"})
    return HTTPException(409, detail={"code": "OPERATION_STATE", "message": str(exc)})


@event_router.get("/registrations")
def registrations(
    event_id: UUID,
    request: Request,
    operations: Service,
    q: str = Query(default="", max_length=160),
    status: str = Query(default="", max_length=24),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int = Query(default=0, ge=0),
) -> dict[str, object]:
    try:
        return operations.registrations(*credentials(request), event_id, q, status, limit, cursor)
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@event_router.post("/imports/preview", status_code=201, dependencies=[Depends(csrf)])
async def preview_import(
    event_id: UUID,
    request: Request,
    operations: Service,
) -> dict[str, object]:
    try:
        body = await request.body()
        if len(body) > 11 * 1024 * 1024:
            raise OperationDenied("Upload a file no larger than 10 MB")
        content_type = request.headers.get("content-type", "")
        if not content_type.lower().startswith("multipart/form-data;"):
            raise OperationDenied("Upload the file as multipart form data")
        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: " + content_type.encode("ascii", "strict") + b"\r\n\r\n" + body
        )
        part = next(
            (
                item
                for item in message.iter_parts()
                if item.get_param("name", header="content-disposition") == "file"
            ),
            None,
        )
        if part is None or not part.get_filename():
            raise OperationDenied("Select a CSV or XLSX file")
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            raise OperationDenied("The multipart file payload is invalid")
        return operations.preview_import(
            *credentials(request), event_id, part.get_filename() or "participants.csv", payload
        )
    except (UnicodeError, AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@event_router.post("/imports/{import_id}/validate", dependencies=[Depends(csrf)])
def validate_import(
    event_id: UUID,
    import_id: UUID,
    body: ImportPolicy,
    request: Request,
    operations: Service,
) -> dict[str, object]:
    try:
        return operations.validate_import(
            *credentials(request), event_id, import_id, **body.model_dump()
        )
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@event_router.post("/imports/{import_id}/commit", status_code=202, dependencies=[Depends(csrf)])
def commit_import(
    event_id: UUID,
    import_id: UUID,
    body: ImportPolicy,
    request: Request,
    operations: Service,
) -> dict[str, object]:
    try:
        return operations.commit_import(
            *credentials(request), event_id, import_id, **body.model_dump()
        )
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@event_router.get("/imports/{import_id}")
def import_status(
    event_id: UUID, import_id: UUID, request: Request, operations: Service
) -> dict[str, object]:
    try:
        return operations.import_status(*credentials(request), event_id, import_id)
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@event_router.get("/imports/{import_id}/errors.csv")
def import_errors(
    event_id: UUID, import_id: UUID, request: Request, operations: Service
) -> Response:
    try:
        content = operations.import_errors_csv(*credentials(request), event_id, import_id)
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="import-{import_id}-errors.csv"'
            },
        )
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@event_router.get("/attendance")
def attendance(event_id: UUID, request: Request, operations: Service) -> dict[str, object]:
    try:
        return operations.attendance(*credentials(request), event_id)
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@event_router.get("/attendance/export.csv")
def attendance_export(event_id: UUID, request: Request, operations: Service) -> Response:
    try:
        content = operations.attendance_csv(*credentials(request), event_id)
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="attendance-{event_id}.csv"'},
        )
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@gate_router.get("/session")
def gate_session(request: Request, operations: Service) -> dict[str, object]:
    try:
        return operations.gate_session(*credentials(request))
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc


@gate_router.post("/redeem", dependencies=[Depends(csrf)])
def redeem(body: RedeemBody, request: Request, operations: Service) -> dict[str, object]:
    try:
        return operations.redeem(
            *credentials(request), body.event_id, body.gate_id, body.credential
        )
    except (AuthDenied, Forbidden, OperationDenied) as exc:
        raise denied(exc) from exc
