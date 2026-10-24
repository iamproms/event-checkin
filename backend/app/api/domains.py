"""Tenant web-domain claims and status; platform activation is separate."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.api.auth import SESSION_COOKIE, csrf
from app.auth.service import AuthDenied, Forbidden
from app.tenancy.domains import DomainDenied, DomainService

router = APIRouter(prefix="/api/v1/domains", tags=["tenant web domains"])


def service(request: Request) -> DomainService:
    result = getattr(request.app.state, "domain_service", None)
    if result is None:
        raise HTTPException(
            503,
            detail={"code": "DOMAINS_UNAVAILABLE", "message": "Domain administration unavailable"},
        )
    return cast(DomainService, result)


Service = Annotated[DomainService, Depends(service)]


class ClaimBody(BaseModel):
    hostname: str


def denied(exc: Exception) -> HTTPException:
    if isinstance(exc, Forbidden):
        return HTTPException(403, detail={"code": "FORBIDDEN", "message": "Access denied"})
    if isinstance(exc, AuthDenied):
        return HTTPException(401, detail={"code": "AUTH_DENIED", "message": "Sign in required"})
    if isinstance(exc, IntegrityError):
        return HTTPException(
            409, detail={"code": "HOSTNAME_CLAIMED", "message": "Hostname is unavailable"}
        )
    if isinstance(exc, DomainDenied):
        return HTTPException(409, detail={"code": "DOMAIN_STATE", "message": str(exc)})
    return HTTPException(422, detail={"code": "INVALID_HOST", "message": "Invalid hostname"})


@router.get("")
def list_domains(request: Request, domain: Service) -> dict[str, object]:
    try:
        rows = domain.status(
            request.state.trusted_hostname, request.cookies.get(SESSION_COOKIE, "")
        )
    except (AuthDenied, Forbidden) as exc:
        raise denied(exc) from exc
    return {
        "domains": [
            {
                "id": str(row.id),
                "hostname": row.hostname,
                "kind": row.kind,
                "ownership": row.verification_state,
                "tls": row.tls_state,
                "routing": row.routing_state,
                "primary": row.is_primary,
                "serving": domain.public_route_serving(row),
                "error_code": row.last_error_code,
            }
            for row in rows
        ]
    }


@router.post("", dependencies=[Depends(csrf)], status_code=201)
def claim(body: ClaimBody, request: Request, domain: Service) -> dict[str, str]:
    try:
        domain_id, hostname, proof = domain.request_claim(
            request.state.trusted_hostname,
            request.cookies.get(SESSION_COOKIE, ""),
            body.hostname,
        )
    except (AuthDenied, Forbidden, DomainDenied, ValueError, IntegrityError) as exc:
        raise denied(exc) from exc
    return {
        "domain_id": str(domain_id),
        "dns_record": f"_eventcheckin-verify.{hostname}",
        "dns_value": proof,
        "state": "reserved",
    }


@router.post("/{domain_id}/check", dependencies=[Depends(csrf)])
def check(domain_id: UUID, request: Request, domain: Service) -> dict[str, str]:
    try:
        job_id = domain.request_check(
            request.state.trusted_hostname, request.cookies.get(SESSION_COOKIE, ""), domain_id
        )
    except (AuthDenied, Forbidden, DomainDenied) as exc:
        raise denied(exc) from exc
    return {"job_id": str(job_id), "state": "pending"}


@router.post("/{domain_id}/renew", dependencies=[Depends(csrf)])
def renew(domain_id: UUID, request: Request, domain: Service) -> dict[str, str]:
    try:
        proof = domain.renew_claim(
            request.state.trusted_hostname, request.cookies.get(SESSION_COOKIE, ""), domain_id
        )
    except (AuthDenied, Forbidden, DomainDenied) as exc:
        raise denied(exc) from exc
    return {"dns_value": proof, "state": "reserved"}
