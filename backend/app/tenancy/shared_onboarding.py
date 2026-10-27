"""Idempotent platform creation of shared-host organizations and owner invites."""

import hashlib
import json
import re
from datetime import timedelta
from urllib.parse import quote
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.address import single_email_address
from app.auth.email import EmailDelivery
from app.auth.security import new_token, token_digest
from app.db.models import (
    PlatformOnboardingRequest,
    StaffInvitation,
    Tenant,
    TenantMembership,
)
from app.tenancy.domains import DomainDenied, DomainService, now

CONTACT_PHONE = re.compile(r"^\+[1-9][0-9]{6,14}$")


class SharedOnboarding:
    def __init__(self, control_engine: Engine, delivery: EmailDelivery) -> None:
        self.engine, self.delivery = control_engine, delivery

    @staticmethod
    def _view(request: PlatformOnboardingRequest) -> dict[str, str]:
        return {
            "organization_id": str(request.tenant_id),
            "organizer_email": request.organizer_email,
            "invitation_delivery_status": request.delivery_status,
            "event_setup_name": request.requested_event_name or "",
        }

    def create(
        self,
        *,
        actor: UUID,
        idempotency_key: UUID,
        name: str,
        organizer_email: str,
        organizer_name: str | None,
        contact_phone: str | None,
        event_name: str | None,
        origin: str,
    ) -> dict[str, str]:
        name = name.strip()
        email = single_email_address(organizer_email)
        organizer_name = (organizer_name or "").strip() or None
        contact_phone = (contact_phone or "").strip() or None
        event_name = (event_name or "").strip() or None
        if (
            not 1 <= len(name) <= 200
            or any(ord(char) < 32 for char in name)
            or (contact_phone is not None and not CONTACT_PHONE.fullmatch(contact_phone))
        ) or any(
            value is not None and (len(value) > limit or any(ord(char) < 32 for char in value))
            for value, limit in ((organizer_name, 160), (contact_phone, 40), (event_name, 200))
        ):
            raise DomainDenied("Invalid organization details")
        digest = hashlib.sha256(
            json.dumps(
                [name, email, organizer_name, contact_phone, event_name],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).digest()
        token = new_token()
        with Session(self.engine) as db, db.begin():
            DomainService._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": str(idempotency_key)},
            )
            existing = db.get(PlatformOnboardingRequest, idempotency_key)
            if existing is not None:
                if existing.actor_user_id != actor or existing.payload_digest != digest:
                    raise DomainDenied("Onboarding request key was used for different details")
                return self._view(existing)
            tenant = Tenant(name=name, slug=f"org-{uuid4().hex[:16]}", status="active")
            db.add(tenant)
            db.flush()
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant.id)}
            )
            invite = StaffInvitation(
                tenant_id=tenant.id,
                email=email,
                role="tenant_owner",
                token_digest=token_digest(token),
                platform_actor_id=actor,
                expires_at=now() + timedelta(hours=48),
            )
            db.add(invite)
            db.flush()
            request = PlatformOnboardingRequest(
                idempotency_key=idempotency_key,
                actor_user_id=actor,
                tenant_id=tenant.id,
                payload_digest=digest,
                organizer_email=email,
                organizer_name=organizer_name,
                contact_phone=contact_phone,
                requested_event_name=event_name,
                invitation_id=invite.id,
                delivery_status="pending",
            )
            db.add(request)
            DomainService._audit(
                db,
                actor,
                tenant.id,
                "shared_organization.created",
                {"invitation_id": str(invite.id)},
            )
            organization_id, invitation_id = tenant.id, invite.id
        destination = f"{origin}/invite#token={quote(token)}&tenant={organization_id}"
        return self._deliver(
            actor, idempotency_key, organization_id, invitation_id, email, name, destination
        )

    def resend(self, actor: UUID, tenant_id: UUID, origin: str) -> dict[str, str]:
        token = new_token()
        with Session(self.engine) as db, db.begin():
            DomainService._assert_platform_actor(db, actor)
            request = db.scalar(
                select(PlatformOnboardingRequest)
                .where(
                    PlatformOnboardingRequest.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            if request is None:
                raise DomainDenied("Shared organization invitation unavailable")
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            if (
                db.scalar(
                    select(TenantMembership.user_id)
                    .where(
                        TenantMembership.tenant_id == tenant_id,
                        TenantMembership.role == "tenant_owner",
                        TenantMembership.status.in_(["active", "pending_mfa"]),
                    )
                    .limit(1)
                )
                is not None
            ):
                raise DomainDenied("Organizer account is already active")
            previous = db.get(StaffInvitation, request.invitation_id, with_for_update=True)
            if previous is not None and previous.accepted_at is None:
                previous.revoked_at = now()
                db.flush()
            invite = StaffInvitation(
                tenant_id=tenant_id,
                email=request.organizer_email,
                role="tenant_owner",
                token_digest=token_digest(token),
                platform_actor_id=actor,
                expires_at=now() + timedelta(hours=48),
            )
            db.add(invite)
            db.flush()
            request.invitation_id = invite.id
            request.delivery_status = "pending"
            tenant = db.get(Tenant, tenant_id)
            assert tenant is not None
            DomainService._audit(
                db,
                actor,
                tenant_id,
                "shared_owner.invitation_reissued",
                {"invitation_id": str(invite.id)},
            )
            key, email, name, invitation_id = (
                request.idempotency_key,
                request.organizer_email,
                tenant.name,
                invite.id,
            )
        destination = f"{origin}/invite#token={quote(token)}&tenant={tenant_id}"
        return self._deliver(actor, key, tenant_id, invitation_id, email, name, destination)

    def _deliver(
        self,
        actor: UUID,
        key: UUID,
        tenant_id: UUID,
        invitation_id: UUID,
        email: str,
        name: str,
        destination: str,
    ) -> dict[str, str]:
        try:
            self.delivery.send_link(
                email,
                f"Welcome to {name} — set up your organizer account",
                destination,
            )
            status = "accepted_by_transport"
        except Exception:
            status = "failed"
        with Session(self.engine) as db, db.begin():
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            request = db.get(PlatformOnboardingRequest, key, with_for_update=True)
            assert request is not None
            if request.invitation_id == invitation_id:
                request.delivery_status = status
                if status == "failed":
                    invite = db.get(StaffInvitation, invitation_id, with_for_update=True)
                    if invite is not None and invite.accepted_at is None:
                        invite.revoked_at = now()
                DomainService._audit(
                    db,
                    actor,
                    tenant_id,
                    "shared_owner.invitation_transport_accepted"
                    if status != "failed"
                    else "shared_owner.invitation_delivery_failed",
                    {"invitation_id": str(invitation_id)},
                )
            return self._view(request)
