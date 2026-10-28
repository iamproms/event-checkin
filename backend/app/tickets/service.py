"""Tenant-authorized ticket lifecycle and worker handlers."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.service import AuthService
from app.branding.assets import AssetInvalid, BrandingStorage
from app.db.models import (
    Event,
    JobRecord,
    Registration,
    RegistrationConsent,
    RegistrationNoticeVersion,
    TenantBranding,
    Ticket,
    TicketAudit,
    TicketDeliveryIntent,
)
from app.db.session import authorized_tenant_session
from app.tickets.crypto import TicketKeyring
from app.tickets.email import DisabledTicketTransport, TicketTransport, ticket_message
from app.worker.jobs import enqueue_job


class TicketDenied(ValueError):
    pass


def _registration(
    db: Session, tenant_id: UUID, event_id: UUID, registration_id: UUID
) -> Registration:
    row = db.scalar(
        select(Registration)
        .where(
            Registration.tenant_id == tenant_id,
            Registration.event_id == event_id,
            Registration.id == registration_id,
        )
        .with_for_update()
    )
    if row is None or row.deleted_at is not None:
        raise TicketDenied("Registration is unavailable")
    return row


def _active(db: Session, tenant_id: UUID, event_id: UUID, registration_id: UUID) -> Ticket | None:
    return db.scalar(
        select(Ticket)
        .where(
            Ticket.tenant_id == tenant_id,
            Ticket.event_id == event_id,
            Ticket.registration_id == registration_id,
            Ticket.status == "active",
        )
        .with_for_update()
    )


def _audit(db: Session, ticket: Ticket, action: str, actor: UUID | None = None) -> None:
    db.add(
        TicketAudit(
            tenant_id=ticket.tenant_id,
            event_id=ticket.event_id,
            ticket_id=ticket.id,
            actor_user_id=actor,
            action=action,
            metadata_json={},
        )
    )


def _queue_delivery(db: Session, ticket: Ticket, kind: str) -> TicketDeliveryIntent:
    intent = TicketDeliveryIntent(
        id=uuid4(),
        tenant_id=ticket.tenant_id,
        event_id=ticket.event_id,
        ticket_id=ticket.id,
        kind=kind,
        status="queued",
        attempts=0,
    )
    db.add(intent)
    db.flush()
    enqueue_job(
        db,
        tenant_id=ticket.tenant_id,
        event_id=ticket.event_id,
        job_type="ticket.deliver",
        idempotency_key=intent.id,
    )
    return intent


class TicketService:
    def __init__(
        self,
        engine: Engine,
        auth: AuthService | None,
        keys: TicketKeyring,
        transport: TicketTransport,
        branding_storage: BrandingStorage | None = None,
    ) -> None:
        self.engine = engine
        self.auth = auth
        self.keys = keys
        self.transport = transport
        self.branding_storage = branding_storage

    def _scope(self, host: str, session_token: str, event_id: UUID) -> tuple[UUID, UUID]:
        if self.auth is None:
            raise TicketDenied("Ticket administration unavailable")
        tenant_id = self.auth.authorize(host, session_token, "attendee.export", event_id)
        actor, _, _ = self.auth.current(host, session_token)
        return tenant_id, actor.id

    def _new_ticket(
        self,
        db: Session,
        registration: Registration,
        actor: UUID | None,
        kind: str,
        *,
        queue_delivery: bool = True,
    ) -> Ticket:
        credential, version = self.keys.new_credential()
        digest = self.keys.digest(credential)
        if digest is None:
            raise TicketDenied("Ticket key is unavailable")
        ticket_id = uuid4()
        ticket = Ticket(
            id=ticket_id,
            tenant_id=registration.tenant_id,
            event_id=registration.event_id,
            registration_id=registration.id,
            key_version=version,
            token_digest=digest,
            token_ciphertext=self.keys.encrypt(
                credential,
                registration.tenant_id,
                registration.event_id,
                registration.id,
                ticket_id,
            ),
            status="active",
        )
        db.add(ticket)
        db.flush()
        _audit(db, ticket, f"ticket.{kind}", actor)
        if queue_delivery:
            _queue_delivery(db, ticket, kind)
        return ticket

    def issue_job(self, db: Session, job: JobRecord) -> None:
        """Called under the worker's tenant-scoped job lock; duplicates are harmless."""
        if job.event_id is None:
            raise TicketDenied("Ticket job lacks event scope")
        registration = _registration(db, job.tenant_id, job.event_id, job.idempotency_key)
        if registration.status != "registered":
            raise TicketDenied("Registration is not active")
        if _active(db, job.tenant_id, job.event_id, registration.id) is not None:
            return
        event = db.scalar(
            select(Event).where(Event.tenant_id == job.tenant_id, Event.id == job.event_id)
        )
        if event is None or event.status != "published":
            raise TicketDenied("Event is unavailable")
        self._new_ticket(
            db,
            registration,
            None,
            "issue",
            queue_delivery=not (
                event.registration_mode == "import_only" and registration.source == "bulk"
            ),
        )

    def issue_bulk(self, host: str, session_token: str, event_id: UUID) -> dict[str, int]:
        """Queue idempotent per-registration work; no QR creation in the request."""
        tenant_id, _ = self._scope(host, session_token, event_id)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            event = db.scalar(select(Event).where(Event.id == event_id))
            if event is None or event.status != "published":
                raise TicketDenied("Publish the event before issuing tickets")
            ids = list(
                db.scalars(
                    select(Registration.id)
                    .where(
                        Registration.event_id == event_id,
                        Registration.status == "registered",
                        Registration.source == "bulk",
                        Registration.deleted_at.is_(None),
                    )
                    .order_by(Registration.id)
                )
            )
            for registration_id in ids:
                enqueue_job(
                    db,
                    tenant_id=tenant_id,
                    event_id=event_id,
                    job_type="ticket.issue",
                    idempotency_key=registration_id,
                )
            return {"eligible": len(ids), "queued_or_existing": len(ids)}

    def send_bulk(self, host: str, session_token: str, event_id: UUID) -> dict[str, int]:
        """One initial delivery intent per issued imported ticket, safely repeatable."""
        if isinstance(self.transport, DisabledTicketTransport):
            raise TicketDenied("Approved transactional ticket delivery is not configured")
        tenant_id, actor = self._scope(host, session_token, event_id)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            event = db.scalar(select(Event).where(Event.id == event_id))
            if event is None or event.status != "published":
                raise TicketDenied("Publish the event before sending tickets")
            tickets = list(
                db.scalars(
                    select(Ticket)
                    .join(
                        Registration,
                        (Registration.tenant_id == Ticket.tenant_id)
                        & (Registration.event_id == Ticket.event_id)
                        & (Registration.id == Ticket.registration_id),
                    )
                    .join(
                        RegistrationConsent,
                        (RegistrationConsent.tenant_id == Registration.tenant_id)
                        & (RegistrationConsent.event_id == Registration.event_id)
                        & (RegistrationConsent.registration_id == Registration.id),
                    )
                    .join(
                        RegistrationNoticeVersion,
                        (RegistrationNoticeVersion.tenant_id == RegistrationConsent.tenant_id)
                        & (RegistrationNoticeVersion.version == RegistrationConsent.notice_version)
                        & (RegistrationNoticeVersion.sha256 == RegistrationConsent.notice_digest)
                        & (
                            RegistrationNoticeVersion.lawful_basis
                            == RegistrationConsent.lawful_basis
                        ),
                    )
                    .where(
                        Ticket.event_id == event_id,
                        Ticket.status == "active",
                        Registration.status == "registered",
                        Registration.source == "bulk",
                        Registration.deleted_at.is_(None),
                        RegistrationNoticeVersion.active.is_(True),
                        RegistrationNoticeVersion.approved_at.is_not(None),
                    )
                    .order_by(Ticket.id)
                    .with_for_update(of=Ticket)
                )
            )
            all_imported_tickets = (
                db.scalar(
                    select(func.count(Ticket.id))
                    .join(
                        Registration,
                        (Registration.tenant_id == Ticket.tenant_id)
                        & (Registration.event_id == Ticket.event_id)
                        & (Registration.id == Ticket.registration_id),
                    )
                    .where(
                        Ticket.event_id == event_id,
                        Ticket.status == "active",
                        Registration.status == "registered",
                        Registration.source == "bulk",
                        Registration.deleted_at.is_(None),
                    )
                )
                or 0
            )
            if len(tickets) != all_imported_tickets:
                raise TicketDenied("Approved import notice evidence is required before sending")
            queued = 0
            for ticket in tickets:
                existing = db.scalar(
                    select(TicketDeliveryIntent.id)
                    .where(
                        TicketDeliveryIntent.tenant_id == tenant_id,
                        TicketDeliveryIntent.event_id == event_id,
                        TicketDeliveryIntent.ticket_id == ticket.id,
                    )
                    .limit(1)
                )
                if existing is None:
                    _queue_delivery(db, ticket, "issue")
                    _audit(db, ticket, "ticket.bulk_send_requested", actor)
                    queued += 1
            return {"issued": len(tickets), "newly_queued": queued}

    def bulk_status(self, host: str, session_token: str, event_id: UUID) -> dict[str, int]:
        tenant_id, _ = self._scope(host, session_token, event_id)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            registrations = (
                db.scalar(
                    select(func.count(Registration.id)).where(
                        Registration.event_id == event_id,
                        Registration.source == "bulk",
                        Registration.status == "registered",
                        Registration.deleted_at.is_(None),
                    )
                )
                or 0
            )
            issued = (
                db.scalar(
                    select(func.count(Ticket.id))
                    .join(
                        Registration,
                        (Registration.tenant_id == Ticket.tenant_id)
                        & (Registration.event_id == Ticket.event_id)
                        & (Registration.id == Ticket.registration_id),
                    )
                    .where(
                        Ticket.event_id == event_id,
                        Ticket.status == "active",
                        Registration.source == "bulk",
                    )
                )
                or 0
            )
            delivery_rows = db.execute(
                select(
                    TicketDeliveryIntent.status,
                    func.count(TicketDeliveryIntent.id),
                )
                .join(
                    Ticket,
                    (Ticket.tenant_id == TicketDeliveryIntent.tenant_id)
                    & (Ticket.event_id == TicketDeliveryIntent.event_id)
                    & (Ticket.id == TicketDeliveryIntent.ticket_id),
                )
                .join(
                    Registration,
                    (Registration.tenant_id == Ticket.tenant_id)
                    & (Registration.event_id == Ticket.event_id)
                    & (Registration.id == Ticket.registration_id),
                )
                .where(
                    TicketDeliveryIntent.event_id == event_id,
                    Ticket.status == "active",
                    Registration.source == "bulk",
                )
                .group_by(TicketDeliveryIntent.status)
            ).all()
            result = {
                "registered": registrations,
                "issued": issued,
                "queued": 0,
                "sent": 0,
                "delivered": 0,
                "failed": 0,
            }
            for state, count in delivery_rows:
                if state in result:
                    result[state] = count
            return result

    def deliver_job(self, _db: Session, job: JobRecord) -> None:
        if job.event_id is None:
            raise TicketDenied("Delivery job lacks event scope")
        # Delivery state is committed independently from the outer job transaction.
        # Otherwise a provider exception would roll back the visible failure state.
        # The intent UUID is the provider idempotency key, so a retry after an
        # ambiguous response must resolve to the same provider message.
        with authorized_tenant_session(self.engine, job.tenant_id) as state_db:
            intent = state_db.scalar(
                select(TicketDeliveryIntent)
                .where(
                    TicketDeliveryIntent.tenant_id == job.tenant_id,
                    TicketDeliveryIntent.event_id == job.event_id,
                    TicketDeliveryIntent.id == job.idempotency_key,
                )
                .with_for_update()
            )
            if intent is None:
                raise TicketDenied("Delivery intent is unavailable")
            if intent.status in {"sent", "delivered"}:
                return
            ticket = state_db.scalar(
                select(Ticket).where(
                    Ticket.tenant_id == job.tenant_id,
                    Ticket.event_id == job.event_id,
                    Ticket.id == intent.ticket_id,
                )
            )
            if ticket is None or ticket.status != "active":
                intent.status = "failed"
                intent.error_code = "TICKET_INACTIVE"
                intent.failed_at = datetime.now(UTC)
                return
            registration = state_db.scalar(
                select(Registration).where(
                    Registration.tenant_id == job.tenant_id,
                    Registration.event_id == job.event_id,
                    Registration.id == ticket.registration_id,
                )
            )
            event = state_db.scalar(
                select(Event).where(Event.tenant_id == job.tenant_id, Event.id == job.event_id)
            )
            tenant = state_db.execute(
                text("SELECT id,name FROM current_active_tenant_profile()")
            ).one_or_none()
            brand = state_db.scalar(
                select(TenantBranding).where(TenantBranding.tenant_id == job.tenant_id)
            )
            if (
                registration is None
                or event is None
                or tenant is None
                or registration.deleted_at is not None
            ):
                intent.status = "failed"
                intent.error_code = "RECIPIENT_UNAVAILABLE"
                intent.failed_at = datetime.now(UTC)
                return
            if registration.source == "bulk":
                evidence = state_db.scalar(
                    select(RegistrationConsent.id)
                    .join(
                        RegistrationNoticeVersion,
                        (RegistrationNoticeVersion.tenant_id == RegistrationConsent.tenant_id)
                        & (RegistrationNoticeVersion.version == RegistrationConsent.notice_version)
                        & (RegistrationNoticeVersion.sha256 == RegistrationConsent.notice_digest)
                        & (
                            RegistrationNoticeVersion.lawful_basis
                            == RegistrationConsent.lawful_basis
                        ),
                    )
                    .where(
                        RegistrationConsent.tenant_id == job.tenant_id,
                        RegistrationConsent.event_id == job.event_id,
                        RegistrationConsent.registration_id == registration.id,
                        RegistrationNoticeVersion.active.is_(True),
                        RegistrationNoticeVersion.approved_at.is_not(None),
                    )
                    .limit(1)
                )
                if evidence is None:
                    intent.status = "failed"
                    intent.error_code = "NOTICE_UNAVAILABLE"
                    intent.failed_at = datetime.now(UTC)
                    return
            credential = self.keys.decrypt(
                ticket.token_ciphertext,
                ticket.key_version,
                ticket.tenant_id,
                ticket.event_id,
                ticket.registration_id,
                ticket.id,
            )
            intent_id = intent.id
            recipient = registration.email
            event_name = event.name
            starts_at = event.starts_at
            timezone = event.timezone
            venue = event.location
            organizer_name = (
                brand.display_name
                if brand and brand.published_version and brand.display_name
                else tenant.name
            )
            sender_name = (
                brand.sender_name
                if brand and brand.published_version and brand.sender_name
                else organizer_name
            )
            primary_color = brand.primary_color if brand and brand.published_version else None
            logo_key = (
                brand.logo_object_key
                if brand and brand.published_version and brand.logo_object_key
                else None
            )
            intent.status = "sending"
            intent.attempts += 1
            intent.error_code = None
            intent.failed_at = None

        try:
            logo_png = None
            if logo_key is not None and self.branding_storage is not None:
                try:
                    logo_png = self.branding_storage.get(logo_key)
                except (AssetInvalid, OSError):
                    # A branding asset outage must not block ticket delivery.
                    logo_png = None
            message = ticket_message(
                intent_id=intent_id,
                tenant_id=job.tenant_id,
                recipient=recipient,
                credential=credential,
                event_name=event_name,
                starts_at=starts_at,
                timezone=timezone,
                venue=venue,
                organizer_name=organizer_name,
                sender_name=sender_name,
                primary_color=primary_color,
                logo_png=logo_png,
            )
            provider_id = self.transport.send(message)
        except Exception:
            with authorized_tenant_session(self.engine, job.tenant_id) as failure_db:
                failed = failure_db.scalar(
                    select(TicketDeliveryIntent)
                    .where(
                        TicketDeliveryIntent.tenant_id == job.tenant_id,
                        TicketDeliveryIntent.event_id == job.event_id,
                        TicketDeliveryIntent.id == job.idempotency_key,
                    )
                    .with_for_update()
                )
                if failed is not None and failed.status not in {"sent", "delivered"}:
                    failed.status = "failed"
                    failed.error_code = "DELIVERY_UNAVAILABLE"
                    failed.failed_at = datetime.now(UTC)
            raise

        with authorized_tenant_session(self.engine, job.tenant_id) as success_db:
            delivered = success_db.scalar(
                select(TicketDeliveryIntent)
                .where(
                    TicketDeliveryIntent.tenant_id == job.tenant_id,
                    TicketDeliveryIntent.event_id == job.event_id,
                    TicketDeliveryIntent.id == job.idempotency_key,
                )
                .with_for_update()
            )
            if delivered is None:
                raise TicketDenied("Delivery intent is unavailable")
            if delivered.status in {"sent", "delivered"}:
                return
            delivered.status = "sent"
            delivered.provider_message_id = provider_id
            delivered.error_code = None
            delivered.failed_at = None
            delivered.sent_at = datetime.now(UTC)
            delivered_ticket = success_db.scalar(
                select(Ticket).where(
                    Ticket.tenant_id == job.tenant_id,
                    Ticket.event_id == job.event_id,
                    Ticket.id == delivered.ticket_id,
                )
            )
            if delivered_ticket is not None:
                _audit(success_db, delivered_ticket, "ticket.sent")

    def status(
        self, host: str, session_token: str, event_id: UUID, registration_id: UUID
    ) -> dict[str, object]:
        tenant_id, _ = self._scope(host, session_token, event_id)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            _registration(db, tenant_id, event_id, registration_id)
            ticket = _active(db, tenant_id, event_id, registration_id)
            if ticket is None:
                return {"ticket_status": "unavailable", "delivery_status": "unavailable"}
            intent = db.scalar(
                select(TicketDeliveryIntent)
                .where(
                    TicketDeliveryIntent.tenant_id == tenant_id,
                    TicketDeliveryIntent.event_id == event_id,
                    TicketDeliveryIntent.ticket_id == ticket.id,
                )
                .order_by(TicketDeliveryIntent.created_at.desc(), TicketDeliveryIntent.id.desc())
            )
            return {
                "ticket_status": ticket.status,
                "delivery_status": intent.status if intent else "unavailable",
                "delivery_error": intent.error_code if intent else None,
            }

    def command(
        self,
        host: str,
        session_token: str,
        event_id: UUID,
        registration_id: UUID,
        action: str,
    ) -> dict[str, object]:
        if action not in {"resend", "reissue", "revoke"}:
            raise TicketDenied("Unsupported ticket action")
        tenant_id, actor = self._scope(host, session_token, event_id)
        if action in {"resend", "reissue"} and isinstance(self.transport, DisabledTicketTransport):
            raise TicketDenied("Ticket delivery is unavailable")
        with authorized_tenant_session(self.engine, tenant_id) as db:
            registration = _registration(db, tenant_id, event_id, registration_id)
            ticket = _active(db, tenant_id, event_id, registration_id)
            if ticket is None:
                raise TicketDenied("No active ticket")
            if action in {"resend", "reissue"}:
                event = db.scalar(
                    select(Event).where(Event.tenant_id == tenant_id, Event.id == event_id)
                )
                if (
                    event is None
                    or event.status != "published"
                    or registration.status != "registered"
                ):
                    raise TicketDenied("Ticket delivery is unavailable for this event")
            if action == "resend":
                recent = db.scalar(
                    select(TicketDeliveryIntent)
                    .where(
                        TicketDeliveryIntent.tenant_id == tenant_id,
                        TicketDeliveryIntent.event_id == event_id,
                        TicketDeliveryIntent.ticket_id == ticket.id,
                    )
                    .order_by(TicketDeliveryIntent.created_at.desc())
                )
                if recent and recent.created_at > datetime.now(UTC) - timedelta(minutes=1):
                    raise TicketDenied("Wait before sending this ticket again")
                _queue_delivery(db, ticket, "resend")
                _audit(db, ticket, "ticket.resend_requested", actor)
                return {"ticket_status": "active", "delivery_status": "queued"}
            ticket.status = "revoked"
            ticket.revoked_at = datetime.now(UTC)
            _audit(
                db,
                ticket,
                "ticket.revoked" if action == "revoke" else "ticket.reissued_from",
                actor,
            )
            db.flush()
            if action == "reissue":
                replacement = self._new_ticket(db, registration, actor, "reissue")
                return {"ticket_status": replacement.status, "delivery_status": "queued"}
            return {"ticket_status": "revoked", "delivery_status": "unavailable"}

    def verify_active(self, tenant_id: UUID, event_id: UUID, credential: str) -> UUID | None:
        """M4 online scanner hook; never returns attendee identity or raw credential."""
        digest = self.keys.digest(credential)
        version = self.keys.version_of(credential)
        if digest is None or version is None:
            return None
        with authorized_tenant_session(self.engine, tenant_id) as db:
            ticket = db.scalar(
                select(Ticket).where(
                    Ticket.tenant_id == tenant_id,
                    Ticket.event_id == event_id,
                    Ticket.key_version == version,
                    Ticket.token_digest == digest,
                    Ticket.status == "active",
                )
            )
            return ticket.id if ticket else None
