"""Web-domain claims and routing. Provider observations never authorize users."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.email import DeliveryUnavailable, DisabledEmailDelivery, EmailDelivery
from app.auth.security import new_token, token_digest
from app.auth.service import AuthService, Forbidden
from app.db.models import (
    DomainReconcileRequest,
    PlatformGrant,
    SecurityAuditEvent,
    StaffInvitation,
    Tenant,
    TenantDomain,
    TenantMembership,
    User,
)
from app.db.session import authorized_tenant_session, normalize_hostname
from app.worker.jobs import enqueue_job

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
OWNER_PROOF_LIFETIME = timedelta(hours=24)
CLAIM_LIFETIME = timedelta(hours=48)
EDGE_SMOKE_LIFETIME = timedelta(minutes=15)


def now() -> datetime:
    return datetime.now(UTC)


def route_eligible(domain: TenantDomain, instant: datetime) -> bool:
    return (
        domain.routing_state == "active"
        and domain.verification_state == "verified"
        and domain.tls_state == "active"
        and domain.edge_ready
        and domain.ownership_valid_until is not None
        and domain.ownership_valid_until > instant
        and domain.tls_valid_until is not None
        and domain.tls_valid_until > instant
        and domain.smoke_checked_at is not None
        and domain.smoke_checked_at > instant - EDGE_SMOKE_LIFETIME
    )


class DomainDenied(ValueError):
    pass


class DomainProvider(Protocol):
    def txt_values(self, hostname: str) -> list[str]: ...
    def certificate_valid_until(self, hostname: str) -> datetime | None: ...
    def edge_mapping_ready(self, hostname: str, tenant_id: UUID) -> bool: ...
    def smoke_check(self, hostname: str, tenant_id: UUID) -> bool: ...


class DisabledDomainProvider:
    """Safe staging/production default until G-06 activates a provider."""

    def txt_values(self, hostname: str) -> list[str]:
        return []

    def certificate_valid_until(self, hostname: str) -> datetime | None:
        return None

    def edge_mapping_ready(self, hostname: str, tenant_id: UUID) -> bool:
        return False

    def smoke_check(self, hostname: str, tenant_id: UUID) -> bool:
        return False


class FixtureDomainProvider:
    """Deterministic local/test DNS, TLS and edge observations from a JSON file.

    This adapter is never enabled by staging/production configuration.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def _row(self, hostname: str) -> dict[str, object]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            row = data.get(hostname, {})
            return row if isinstance(row, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def txt_values(self, hostname: str) -> list[str]:
        value = self._row(hostname).get("txt", [])
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

    def certificate_valid_until(self, hostname: str) -> datetime | None:
        value = self._row(hostname).get("certificate_valid_until")
        if not isinstance(value, str):
            return None
        try:
            expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return expiry if expiry.tzinfo is not None else None
        except ValueError:
            return None

    def edge_mapping_ready(self, hostname: str, tenant_id: UUID) -> bool:
        row = self._row(hostname)
        return row.get("tenant_id") == str(tenant_id) and row.get("edge_ready") is True

    def smoke_check(self, hostname: str, tenant_id: UUID) -> bool:
        row = self._row(hostname)
        return row.get("tenant_id") == str(tenant_id) and row.get("smoke_ok") is True


@dataclass(frozen=True)
class DomainObservation:
    claim_digest: bytes
    ownership_ok: bool
    certificate_until: datetime | None
    edge_ready: bool
    smoke_ok: bool


def observe(domain: TenantDomain, provider: DomainProvider) -> DomainObservation:
    # TXT proof is public DNS data. Only its digest is persisted; no queue
    # message or log contains the raw claim token.
    proof = f"_eventcheckin-verify.{domain.hostname}"
    ownership = bool(domain.claim_digest) and any(
        hashlib.sha256(value.encode("ascii")).digest() == domain.claim_digest
        for value in provider.txt_values(proof)
        if value.isascii()
    )
    valid_until = provider.certificate_valid_until(domain.hostname)
    return DomainObservation(
        claim_digest=domain.claim_digest or b"",
        ownership_ok=ownership,
        certificate_until=valid_until,
        edge_ready=provider.edge_mapping_ready(domain.hostname, domain.tenant_id),
        smoke_ok=provider.smoke_check(domain.hostname, domain.tenant_id),
    )


def queue_reconcile(db: Session, domain: TenantDomain) -> UUID:
    job_id = enqueue_job(
        db, tenant_id=domain.tenant_id, job_type="domain.reconcile", idempotency_key=uuid4()
    )
    db.add(DomainReconcileRequest(tenant_id=domain.tenant_id, job_id=job_id, domain_id=domain.id))
    domain.next_reconcile_at = now() + timedelta(minutes=5)
    db.flush()
    return job_id


def schedule_due_reconciliations(control_engine: Engine, limit: int = 50) -> int:
    """Recover from missed timers without Redis being the source of truth."""
    with Session(control_engine) as db, db.begin():
        due = list(
            db.scalars(
                select(TenantDomain)
                .where(
                    TenantDomain.next_reconcile_at <= now(),
                    TenantDomain.routing_state.in_(["reserved", "ready", "active", "deactivated"]),
                )
                .order_by(TenantDomain.next_reconcile_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        for domain in due:
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(domain.tenant_id)}
            )
            queue_reconcile(db, domain)
        return len(due)


class DomainService:
    def __init__(
        self,
        control_engine: Engine,
        runtime_engine: Engine,
        auth: AuthService | None,
        provider: DomainProvider,
        fallback_suffix: str,
    ) -> None:
        self.control_engine = control_engine
        self.runtime_engine = runtime_engine
        self.auth = auth
        self.provider = provider
        self.fallback_suffix = normalize_hostname(fallback_suffix)

    def _auth(self) -> AuthService:
        if self.auth is None:
            raise DomainDenied("Tenant authorization unavailable")
        return self.auth

    def public_route_serving(self, domain: TenantDomain) -> bool:
        """Match the request resolver, including the current tenant status."""
        with self.runtime_engine.connect() as db:
            resolved = cast(
                UUID | None,
                db.scalar(
                    text("SELECT resolve_active_tenant_domain(:hostname)"),
                    {"hostname": domain.hostname},
                ),
            )
        return resolved == domain.tenant_id

    def _authorize_domain(self, host: str, token: str) -> UUID:
        try:
            return self._auth().authorize(host, token, "tenant.domain.manage")
        except Forbidden:
            # Only the owner on an active fallback route can recover a
            # suspended tenant; authorize() checks that narrower permission.
            return self._auth().authorize(host, token, "tenant.domain.recover")

    @staticmethod
    def _audit(
        db: Session,
        actor: UUID | None,
        tenant: UUID,
        action: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        db.add(
            SecurityAuditEvent(
                actor_user_id=actor, tenant_id=tenant, action=action, metadata_json=metadata or {}
            )
        )

    @staticmethod
    def _assert_platform_actor(db: Session, actor: UUID) -> None:
        grant = db.scalar(
            select(PlatformGrant.id)
            .join(User, User.id == PlatformGrant.user_id)
            .where(
                PlatformGrant.user_id == actor,
                PlatformGrant.operation == "tenant.provision",
                PlatformGrant.tenant_id.is_(None),
                PlatformGrant.valid_from <= now(),
                PlatformGrant.valid_until > now(),
                PlatformGrant.revoked_at.is_(None),
                User.status == "active",
            )
            .limit(1)
        )
        if grant is None:
            raise DomainDenied("Platform authorization expired")

    def provision(self, actor: UUID, name: str, slug: str) -> tuple[UUID, UUID, str, str]:
        if not name.strip() or len(name) > 200 or not SLUG.fullmatch(slug):
            raise DomainDenied("Invalid tenant name or slug")
        host = normalize_hostname(f"{slug}.{self.fallback_suffix}")
        token = new_token()
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            tenant = Tenant(name=name.strip(), slug=slug, status="provisioning")
            db.add(tenant)
            db.flush()
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant.id)}
            )
            domain = TenantDomain(
                tenant_id=tenant.id,
                hostname=host,
                kind="fallback",
                verification_state="pending",
                tls_state="pending",
                routing_state="reserved",
                claim_digest=token_digest(token),
                claim_expires_at=now() + CLAIM_LIFETIME,
            )
            db.add(domain)
            db.flush()
            queue_reconcile(db, domain)
            self._audit(db, actor, tenant.id, "tenant.provisioned", {"domain_id": str(domain.id)})
            return tenant.id, domain.id, host, token

    def request_claim(
        self, host: str, session_token: str, requested_hostname: str
    ) -> tuple[UUID, str, str]:
        tenant_id = self._authorize_domain(host, session_token)
        actor, _, _ = self._auth().current(host, session_token)
        candidate = normalize_hostname(requested_hostname)
        if (
            candidate == normalize_hostname(host)
            or candidate == self.fallback_suffix
            or candidate.endswith(f".{self.fallback_suffix}")
        ):
            raise DomainDenied("Platform-owned hostname is reserved")
        token = new_token()
        with Session(self.control_engine) as db, db.begin():
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            domain = TenantDomain(
                tenant_id=tenant_id,
                hostname=candidate,
                kind="custom",
                verification_state="pending",
                tls_state="pending",
                routing_state="reserved",
                claim_digest=token_digest(token),
                claim_expires_at=now() + CLAIM_LIFETIME,
            )
            db.add(domain)
            db.flush()
            queue_reconcile(db, domain)
            self._audit(
                db, actor.id, tenant_id, "domain.claim_requested", {"domain_id": str(domain.id)}
            )
            domain_id = domain.id
        return domain_id, candidate, token

    def status(self, host: str, session_token: str) -> list[TenantDomain]:
        tenant_id = self._authorize_domain(host, session_token)
        with authorized_tenant_session(self.runtime_engine, tenant_id) as db:
            rows = list(db.scalars(select(TenantDomain).order_by(TenantDomain.created_at)))
            for row in rows:
                db.expunge(row)
            return rows

    def request_check(self, host: str, session_token: str, domain_id: UUID) -> UUID:
        tenant_id = self._authorize_domain(host, session_token)
        actor, _, _ = self._auth().current(host, session_token)
        with Session(self.control_engine) as db, db.begin():
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            domain = db.scalar(
                select(TenantDomain)
                .where(TenantDomain.id == domain_id, TenantDomain.tenant_id == tenant_id)
                .with_for_update()
            )
            if domain is None:
                raise DomainDenied("Domain unavailable")
            job_id = queue_reconcile(db, domain)
            self._audit(
                db,
                actor.id,
                tenant_id,
                "domain.check_requested",
                {"domain_id": str(domain_id), "job_id": str(job_id)},
            )
            return job_id

    @staticmethod
    def _renew_locked(db: Session, domain: TenantDomain, actor: UUID) -> str:
        if domain.routing_state == "active":
            raise DomainDenied("Deactivate an active route before renewing its proof")
        proof = new_token()
        domain.claim_digest = token_digest(proof)
        domain.claim_expires_at = now() + CLAIM_LIFETIME
        domain.verification_state = "pending"
        domain.ownership_checked_at = None
        domain.ownership_valid_until = None
        domain.routing_state = "reserved"
        domain.activated_at = None
        domain.last_error_code = None
        queue_reconcile(db, domain)
        DomainService._audit(
            db, actor, domain.tenant_id, "domain.proof_renewed", {"domain_id": str(domain.id)}
        )
        return proof

    def renew_claim(self, host: str, session_token: str, domain_id: UUID) -> str:
        tenant_id = self._authorize_domain(host, session_token)
        actor, _, _ = self._auth().current(host, session_token)
        with Session(self.control_engine) as db, db.begin():
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            domain = db.scalar(
                select(TenantDomain)
                .where(
                    TenantDomain.tenant_id == tenant_id,
                    TenantDomain.id == domain_id,
                )
                .with_for_update()
            )
            if domain is None or domain.kind != "custom":
                raise DomainDenied("Custom domain unavailable")
            return self._renew_locked(db, domain, actor.id)

    def platform_renew_claim(self, actor: UUID, tenant_id: UUID, domain_id: UUID) -> str:
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            domain = db.scalar(
                select(TenantDomain)
                .where(
                    TenantDomain.tenant_id == tenant_id,
                    TenantDomain.id == domain_id,
                )
                .with_for_update()
            )
            if domain is None:
                raise DomainDenied("Domain unavailable")
            return self._renew_locked(db, domain, actor)

    def platform_status(self, actor: UUID, tenant_id: UUID) -> list[TenantDomain]:
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            rows = list(
                db.scalars(
                    select(TenantDomain)
                    .where(TenantDomain.tenant_id == tenant_id)
                    .order_by(TenantDomain.created_at)
                )
            )
            for row in rows:
                db.expunge(row)
            return rows

    def platform_request_check(self, actor: UUID, tenant_id: UUID, domain_id: UUID) -> UUID:
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            domain = db.scalar(
                select(TenantDomain)
                .where(
                    TenantDomain.tenant_id == tenant_id,
                    TenantDomain.id == domain_id,
                )
                .with_for_update()
            )
            if domain is None:
                raise DomainDenied("Domain unavailable")
            job_id = queue_reconcile(db, domain)
            self._audit(
                db,
                actor,
                tenant_id,
                "domain.check_requested",
                {"domain_id": str(domain_id), "job_id": str(job_id)},
            )
            return job_id

    def reconcile(self, job_id: UUID, tenant_id: UUID) -> None:
        # A worker resolves the domain from a composite tenant/job FK, not from
        # unverified queue payload. Provider I/O occurs outside the DB lock.
        with authorized_tenant_session(self.runtime_engine, tenant_id) as db:
            request = db.get(DomainReconcileRequest, job_id)
            if request is None or request.tenant_id != tenant_id:
                raise DomainDenied("Unknown domain job")
            domain = db.get(TenantDomain, request.domain_id)
            if domain is None or domain.tenant_id != tenant_id:
                raise DomainDenied("Unknown domain")
            db.expunge(domain)
        observation_started_at = now()
        result = observe(domain, self.provider)
        checked_at = now()
        with Session(self.control_engine) as db, db.begin():
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            live = db.scalar(
                select(TenantDomain)
                .where(
                    TenantDomain.id == domain.id,
                    TenantDomain.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            if (
                live is None
                or live.claim_digest != result.claim_digest
                or (
                    live.ownership_checked_at is not None
                    and live.ownership_checked_at > observation_started_at
                )
            ):
                return
            ownership_ok = result.ownership_ok and (
                (live.claim_expires_at is not None and live.claim_expires_at > checked_at)
                or live.activated_at is not None
            )
            tls_ok = result.certificate_until is not None and result.certificate_until > checked_at
            live.verification_state = "verified" if ownership_ok else "failed"
            live.ownership_checked_at = checked_at
            live.ownership_valid_until = checked_at + OWNER_PROOF_LIFETIME if ownership_ok else None
            live.tls_state = "active" if tls_ok else "failed"
            live.tls_checked_at = checked_at
            live.tls_valid_until = result.certificate_until if tls_ok else None
            live.edge_ready = result.edge_ready
            live.smoke_checked_at = checked_at if result.smoke_ok else None
            live.updated_at = checked_at
            live.next_reconcile_at = checked_at + timedelta(minutes=5)
            if ownership_ok and tls_ok and result.edge_ready and result.smoke_ok:
                if live.routing_state in {"reserved", "deactivated"}:
                    live.routing_state = "ready"
                live.last_error_code = None
            else:
                if live.routing_state == "active":
                    live.routing_state = "deactivated"
                    was_primary = live.is_primary
                    live.is_primary = False
                    db.flush()
                    if was_primary and live.kind == "custom":
                        fallback = db.scalar(
                            select(TenantDomain)
                            .where(
                                TenantDomain.tenant_id == tenant_id,
                                TenantDomain.kind == "fallback",
                                TenantDomain.routing_state == "active",
                            )
                            .with_for_update()
                        )
                        if fallback is not None and route_eligible(fallback, checked_at):
                            fallback.is_primary = True
                live.last_error_code = (
                    "OWNERSHIP_FAILED"
                    if not ownership_ok
                    else "TLS_FAILED"
                    if not tls_ok
                    else "EDGE_NOT_READY"
                    if not result.edge_ready
                    else "SMOKE_FAILED"
                )
            self._audit(
                db,
                None,
                tenant_id,
                "domain.reconciled",
                {"domain_id": str(live.id), "result": live.last_error_code or "ready"},
            )

    def activate(self, actor: UUID, tenant_id: UUID, domain_id: UUID) -> None:
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            tenant = db.get(Tenant, tenant_id, with_for_update=True)
            domain = db.scalar(
                select(TenantDomain)
                .where(
                    TenantDomain.id == domain_id,
                    TenantDomain.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            instant = now()
            if (
                tenant is None
                or tenant.status not in {"provisioning", "active"}
                or domain is None
                or domain.routing_state != "ready"
                or domain.verification_state != "verified"
                or domain.tls_state != "active"
                or not domain.edge_ready
                or domain.smoke_checked_at is None
                or domain.smoke_checked_at <= instant - timedelta(minutes=5)
                or domain.ownership_checked_at is None
                or domain.ownership_checked_at <= instant - timedelta(minutes=5)
                or domain.tls_checked_at is None
                or domain.tls_checked_at <= instant - timedelta(minutes=5)
                or domain.ownership_valid_until is None
                or domain.ownership_valid_until <= instant
                or domain.tls_valid_until is None
                or domain.tls_valid_until <= instant
            ):
                raise DomainDenied("Domain is not ready for activation")
            if domain.kind == "custom":
                fallback = db.scalar(
                    select(TenantDomain)
                    .where(
                        TenantDomain.tenant_id == tenant_id,
                        TenantDomain.kind == "fallback",
                        TenantDomain.routing_state == "active",
                    )
                    .with_for_update()
                )
                if fallback is None or not route_eligible(fallback, instant):
                    raise DomainDenied("A working fallback route is required")
            for old in db.scalars(
                select(TenantDomain)
                .where(TenantDomain.tenant_id == tenant_id, TenantDomain.is_primary.is_(True))
                .with_for_update()
            ):
                old.is_primary = False
            db.flush()
            domain.routing_state = "active"
            domain.is_primary = True
            domain.activated_at = instant
            tenant.status = "active"
            self._audit(db, actor, tenant_id, "domain.activated", {"domain_id": str(domain_id)})

    def deactivate(self, actor: UUID, tenant_id: UUID, domain_id: UUID) -> None:
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            domain = db.scalar(
                select(TenantDomain)
                .where(TenantDomain.id == domain_id, TenantDomain.tenant_id == tenant_id)
                .with_for_update()
            )
            if domain is None or domain.routing_state != "active":
                raise DomainDenied("Domain is not active")
            fallback = db.scalar(
                select(TenantDomain)
                .where(
                    TenantDomain.tenant_id == tenant_id,
                    TenantDomain.kind == "fallback",
                    TenantDomain.routing_state == "active",
                )
                .with_for_update()
            )
            if fallback is None or fallback.id == domain.id or not route_eligible(fallback, now()):
                raise DomainDenied("A working fallback route is required")
            was_primary = domain.is_primary
            domain.routing_state = "deactivated"
            domain.is_primary = False
            db.flush()
            if was_primary:
                fallback.is_primary = True
            self._audit(db, actor, tenant_id, "domain.deactivated", {"domain_id": str(domain_id)})

    def issue_first_owner(
        self, actor: UUID, tenant_id: UUID, email: str, delivery: EmailDelivery
    ) -> None:
        from urllib.parse import quote

        from app.auth.address import single_email_address

        recipient = single_email_address(email)
        if isinstance(delivery, DisabledEmailDelivery):
            raise DeliveryUnavailable("Transactional email delivery is not configured")
        token = new_token()
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            tenant = db.get(Tenant, tenant_id, with_for_update=True)
            fallback = db.scalar(
                select(TenantDomain).where(
                    TenantDomain.tenant_id == tenant_id,
                    TenantDomain.kind == "fallback",
                    TenantDomain.routing_state == "active",
                )
            )
            if tenant is None or tenant.status != "active" or fallback is None:
                raise DomainDenied("Fallback route is not active")
            for expired in db.scalars(
                select(StaffInvitation)
                .where(
                    StaffInvitation.tenant_id == tenant_id,
                    StaffInvitation.role == "tenant_owner",
                    StaffInvitation.platform_actor_id.is_not(None),
                    StaffInvitation.accepted_at.is_(None),
                    StaffInvitation.revoked_at.is_(None),
                    StaffInvitation.expires_at <= now(),
                )
                .with_for_update()
            ):
                expired.revoked_at = now()
            db.flush()
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
                raise DomainDenied("Initial owner already accepted")
            if (
                db.scalar(
                    select(StaffInvitation.id)
                    .where(
                        StaffInvitation.tenant_id == tenant_id,
                        StaffInvitation.role == "tenant_owner",
                        StaffInvitation.accepted_at.is_(None),
                        StaffInvitation.revoked_at.is_(None),
                        StaffInvitation.expires_at > now(),
                    )
                    .limit(1)
                )
                is not None
            ):
                raise DomainDenied("An initial-owner invitation is already pending")
            invite = StaffInvitation(
                tenant_id=tenant_id,
                email=recipient,
                role="tenant_owner",
                token_digest=token_digest(token),
                platform_actor_id=actor,
                expires_at=now() + timedelta(hours=48),
            )
            db.add(invite)
            db.flush()
            self._audit(
                db, actor, tenant_id, "owner.invitation_issued", {"invitation_id": str(invite.id)}
            )
            destination = f"https://{fallback.hostname}/invite#token={quote(token)}"
            invitation_id = invite.id
        self._deliver_owner(actor, tenant_id, invitation_id, recipient, destination, delivery)

    def reissue_first_owner(self, actor: UUID, tenant_id: UUID, delivery: EmailDelivery) -> None:
        from urllib.parse import quote

        if isinstance(delivery, DisabledEmailDelivery):
            raise DeliveryUnavailable("Transactional email delivery is not configured")
        token = new_token()
        with Session(self.control_engine) as db, db.begin():
            self._assert_platform_actor(db, actor)
            db.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            tenant = db.get(Tenant, tenant_id, with_for_update=True)
            fallback = db.scalar(
                select(TenantDomain).where(
                    TenantDomain.tenant_id == tenant_id,
                    TenantDomain.kind == "fallback",
                    TenantDomain.routing_state == "active",
                )
            )
            if tenant is None or tenant.status != "active" or fallback is None:
                raise DomainDenied("Fallback route is not active")
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
                raise DomainDenied("Initial owner already accepted")
            old = db.scalar(
                select(StaffInvitation)
                .where(
                    StaffInvitation.tenant_id == tenant_id,
                    StaffInvitation.role == "tenant_owner",
                    StaffInvitation.platform_actor_id.is_not(None),
                    StaffInvitation.accepted_at.is_(None),
                    StaffInvitation.revoked_at.is_(None),
                    StaffInvitation.expires_at > now(),
                )
                .with_for_update()
            )
            if old is None:
                raise DomainDenied("No pending initial-owner invitation")
            old.revoked_at = now()
            db.flush()
            replacement = StaffInvitation(
                tenant_id=tenant_id,
                email=old.email,
                role="tenant_owner",
                token_digest=token_digest(token),
                platform_actor_id=actor,
                expires_at=now() + timedelta(hours=48),
            )
            db.add(replacement)
            db.flush()
            self._audit(
                db,
                actor,
                tenant_id,
                "owner.invitation_reissued",
                {
                    "revoked_invitation_id": str(old.id),
                    "invitation_id": str(replacement.id),
                },
            )
            recipient = str(old.email)
            destination = f"https://{fallback.hostname}/invite#token={quote(token)}"
            new_id = replacement.id
        self._deliver_owner(actor, tenant_id, new_id, recipient, destination, delivery)

    def _deliver_owner(
        self,
        actor: UUID,
        tenant_id: UUID,
        invitation_id: UUID,
        recipient: str,
        destination: str,
        delivery: EmailDelivery,
    ) -> None:
        try:
            delivery.send_link(recipient, "Your owner invitation", destination)
        except Exception:
            # SMTP acknowledgement can be ambiguous. Revoke this exact token
            # so a partial send cannot leave a second usable invitation.
            with Session(self.control_engine) as db, db.begin():
                db.execute(
                    text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
                )
                invite = db.scalar(
                    select(StaffInvitation)
                    .where(
                        StaffInvitation.tenant_id == tenant_id,
                        StaffInvitation.id == invitation_id,
                    )
                    .with_for_update()
                )
                if invite is not None and invite.accepted_at is None:
                    invite.revoked_at = now()
                self._audit(
                    db,
                    actor,
                    tenant_id,
                    "owner.invitation_delivery_failed",
                    {
                        "invitation_id": str(invitation_id),
                    },
                )
            raise DeliveryUnavailable("Transactional email delivery failed") from None
