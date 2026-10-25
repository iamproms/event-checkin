"""Tenant branding API. Public data and logo are resolved only from trusted host."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from app.api.auth import SESSION_COOKIE, csrf
from app.auth.service import AuthDenied, Forbidden
from app.branding.assets import MAX_UPLOAD_BYTES, AssetInvalid
from app.branding.contrast import ColorInvalid
from app.branding.service import BrandingConflict, BrandingInvalid, BrandingService
from app.db.session import TenantResolutionError

router = APIRouter(prefix="/api/v1/branding", tags=["tenant branding"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftBody(StrictBody):
    revision: int
    display_name: str
    primary_color: str | None = None
    accent_color: str | None = None
    sender_name: str


class PublishBody(StrictBody):
    revision: int


def service(request: Request) -> BrandingService:
    instance = getattr(request.app.state, "branding_service", None)
    if instance is None:
        raise HTTPException(
            503, detail={"code": "BRANDING_UNAVAILABLE", "message": "Branding is unavailable"}
        )
    return cast(BrandingService, instance)


Service = Annotated[BrandingService, Depends(service)]


def credentials(request: Request) -> tuple[str, str]:
    return request.state.trusted_hostname, request.cookies.get(SESSION_COOKIE, "")


def denied(exc: Exception) -> HTTPException:
    if isinstance(exc, Forbidden):
        return HTTPException(403, detail={"code": "FORBIDDEN", "message": "Access denied"})
    if isinstance(exc, AuthDenied):
        return HTTPException(401, detail={"code": "AUTH_DENIED", "message": "Sign in required"})
    if isinstance(exc, TenantResolutionError):
        return HTTPException(
            421, detail={"code": "UNRECOGNIZED_HOST", "message": "Host unavailable"}
        )
    if isinstance(exc, BrandingConflict):
        return HTTPException(409, detail={"code": "BRANDING_CONFLICT", "message": str(exc)})
    if isinstance(exc, (BrandingInvalid, AssetInvalid, ColorInvalid)):
        return HTTPException(422, detail={"code": "BRANDING_INVALID", "message": str(exc)})
    return HTTPException(500, detail={"code": "BRANDING_ERROR", "message": "Branding failed"})


@router.get("/public")
def public(request: Request, branding: Service) -> dict[str, object]:
    try:
        return branding.public(request.state.trusted_hostname)
    except (TenantResolutionError, BrandingInvalid) as exc:
        raise denied(exc) from exc


@router.get("/public/logo")
def published_logo(request: Request, branding: Service) -> Response:
    try:
        data = branding.logo(request.state.trusted_hostname)
    except (TenantResolutionError, BrandingInvalid) as exc:
        raise denied(exc) from exc
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/draft")
def draft(request: Request, branding: Service) -> dict[str, object]:
    try:
        return branding.get_draft(*credentials(request))
    except (AuthDenied, Forbidden, BrandingInvalid) as exc:
        raise denied(exc) from exc


@router.put("/draft", dependencies=[Depends(csrf)])
def save_draft(body: DraftBody, request: Request, branding: Service) -> dict[str, object]:
    try:
        return branding.save_draft(*credentials(request), **body.model_dump())
    except (AuthDenied, Forbidden, BrandingInvalid, BrandingConflict, ColorInvalid) as exc:
        raise denied(exc) from exc


@router.get("/draft/logo")
def draft_logo(request: Request, branding: Service) -> Response:
    try:
        data = branding.logo(*credentials(request))
    except (AuthDenied, Forbidden, BrandingInvalid) as exc:
        raise denied(exc) from exc
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.put("/logo", dependencies=[Depends(csrf)])
async def upload_logo(request: Request, branding: Service) -> dict[str, object]:
    # Stream a bounded body; Content-Length is not trusted.
    chunks = bytearray()
    async for part in request.stream():
        if len(chunks) + len(part) > MAX_UPLOAD_BYTES:
            raise denied(AssetInvalid("Logo must be smaller than 2 MB."))
        chunks.extend(part)
    try:
        return await run_in_threadpool(
            branding.upload_logo,
            *credentials(request),
            bytes(chunks),
            request.headers.get("content-type", ""),
        )
    except (AuthDenied, Forbidden, BrandingInvalid, AssetInvalid) as exc:
        raise denied(exc) from exc


@router.delete("/logo", dependencies=[Depends(csrf)])
def remove_logo(request: Request, branding: Service) -> dict[str, object]:
    try:
        return branding.remove_logo(*credentials(request))
    except (AuthDenied, Forbidden, BrandingInvalid) as exc:
        raise denied(exc) from exc


@router.post("/publish", dependencies=[Depends(csrf)])
def publish(body: PublishBody, request: Request, branding: Service) -> dict[str, object]:
    try:
        return branding.publish(*credentials(request), body.revision)
    except (AuthDenied, Forbidden, BrandingInvalid, BrandingConflict, ColorInvalid) as exc:
        raise denied(exc) from exc


@router.get("/history")
def history(request: Request, branding: Service) -> dict[str, object]:
    try:
        return {
            "versions": branding.history(*credentials(request)),
            "audit": branding.audit_history(*credentials(request)),
        }
    except (AuthDenied, Forbidden) as exc:
        raise denied(exc) from exc


@router.post("/restore/{version}", dependencies=[Depends(csrf)])
def restore(version: int, request: Request, branding: Service) -> dict[str, object]:
    try:
        return branding.restore(*credentials(request), version)
    except (AuthDenied, Forbidden, BrandingInvalid, BrandingConflict, ColorInvalid) as exc:
        raise denied(exc) from exc
