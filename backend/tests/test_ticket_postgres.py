"""M3-02 ticket lifecycle, concurrency and delivery against real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session
from test_registration_postgres import PermitLimiter, published, seed_notice, submit
from test_tenancy_postgres import Harness

from app.db.models import JobRecord, Registration, Ticket, TicketDeliveryIntent
from app.db.session import authorized_tenant_session
from app.registration.service import RegistrationService
from app.tickets.crypto import TicketKeyring
from app.tickets.email import MemoryTicketTransport, TicketDeliveryUnavailable
from app.tickets.service import TicketDenied, TicketService
from app.worker.jobs import execute_job

pytestmark = pytest.mark.postgres
pytest_plugins = ("test_tenancy_postgres",)


def setup_registration(pg: Harness) -> tuple[UUID, str, str, UUID, UUID]:
    tenant, host, session, event_id, version = published(pg)
    seed_notice(pg, tenant)
    registrations = RegistrationService(pg.runtime, PermitLimiter(), issuance_ready=True)
    submit(registrations, host, version)
    with Session(pg.owner) as db:
        registration_id = db.scalar(
            select(Registration.id).where(
                Registration.tenant_id == tenant, Registration.event_id == event_id
            )
        )
    assert isinstance(registration_id, UUID)
    return tenant, host, session, event_id, registration_id


def test_issue_is_concurrent_safe_and_delivery_is_idempotent(pg: Harness) -> None:
    tenant, _host, _session, event_id, registration_id = setup_registration(pg)
    transport = MemoryTicketTransport()
    service = TicketService(pg.runtime, pg.auth, TicketKeyring({1: b"k" * 32}, 1), transport)
    with Session(pg.owner) as db:
        issue_job = db.scalar(
            select(JobRecord).where(
                JobRecord.job_type == "ticket.issue",
                JobRecord.idempotency_key == registration_id,
            )
        )
        assert issue_job is not None
        db.expunge(issue_job)

    def issue(_: int) -> None:
        with authorized_tenant_session(pg.runtime, tenant) as db:
            service.issue_job(db, issue_job)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(issue, range(2)))
    with Session(pg.owner) as db:
        assert (
            db.scalar(
                text("""SELECT count(*) FROM tickets
              WHERE tenant_id=:tenant AND event_id=:event AND registration_id=:registration
                AND status='active'"""),
                {"tenant": tenant, "event": event_id, "registration": registration_id},
            )
            == 1
        )
        delivery_job = db.scalar(
            select(JobRecord).where(
                JobRecord.job_type == "ticket.deliver",
                JobRecord.tenant_id == tenant,
                JobRecord.event_id == event_id,
            )
        )
        assert delivery_job is not None
        db.expunge(delivery_job)
    with authorized_tenant_session(pg.runtime, tenant) as db:
        service.deliver_job(db, delivery_job)
    with authorized_tenant_session(pg.runtime, tenant) as db:
        service.deliver_job(db, delivery_job)
    assert len(transport.messages) == 1
    message = next(iter(transport.messages.values()))
    assert registration_id.hex not in message.html
    assert b"PNG" in message.qr_png[:16]
    with Session(pg.owner) as db:
        intent = db.scalar(
            select(TicketDeliveryIntent).where(
                TicketDeliveryIntent.tenant_id == tenant,
                TicketDeliveryIntent.event_id == event_id,
            )
        )
        assert intent is not None and intent.status == "sent" and intent.attempts == 1
    with pytest.raises(IntegrityError, match="Ticket credential is immutable"):
        with authorized_tenant_session(pg.runtime, tenant) as db:
            db.execute(
                text(
                    "UPDATE tickets SET token_digest=decode(repeat('00',32),'hex') "
                    "WHERE tenant_id=:tenant"
                ),
                {"tenant": tenant},
            )
    with pytest.raises(ProgrammingError):
        with authorized_tenant_session(pg.runtime, tenant) as db:
            db.execute(
                text(
                    "UPDATE ticket_delivery_intents SET ticket_id=gen_random_uuid() "
                    "WHERE tenant_id=:tenant"
                ),
                {"tenant": tenant},
            )


def test_resend_reissue_revoke_and_cross_tenant_scope(pg: Harness) -> None:
    tenant, host, session, event_id, registration_id = setup_registration(pg)
    service = TicketService(
        pg.runtime,
        pg.auth,
        TicketKeyring({1: b"q" * 32, 2: b"r" * 32}, 2),
        MemoryTicketTransport(),
    )
    with Session(pg.owner) as db:
        job = db.scalar(
            select(JobRecord).where(
                JobRecord.job_type == "ticket.issue",
                JobRecord.idempotency_key == registration_id,
            )
        )
        assert job is not None
        db.expunge(job)
    with authorized_tenant_session(pg.runtime, tenant) as db:
        service.issue_job(db, job)
    with Session(pg.owner) as db:
        initial_id = db.scalar(
            select(Ticket.id).where(
                Ticket.tenant_id == tenant,
                Ticket.event_id == event_id,
                Ticket.registration_id == registration_id,
                Ticket.status == "active",
            )
        )
        assert isinstance(initial_id, UUID)
    # The first delivery was just queued, so immediate resend is deliberately throttled.
    with pytest.raises(TicketDenied, match="Wait"):
        service.command(host, session, event_id, registration_id, "resend")
    replacement = service.command(host, session, event_id, registration_id, "reissue")
    assert replacement == {"ticket_status": "active", "delivery_status": "queued"}
    with Session(pg.owner) as db:
        current_id = db.scalar(
            select(Ticket.id).where(
                Ticket.tenant_id == tenant,
                Ticket.event_id == event_id,
                Ticket.registration_id == registration_id,
                Ticket.status == "active",
            )
        )
        assert current_id != initial_id
        assert (
            db.scalar(
                text("SELECT count(*) FROM tickets WHERE registration_id=:id AND status='revoked'"),
                {"id": registration_id},
            )
            == 1
        )
        active = db.scalar(
            select(Ticket).where(
                Ticket.tenant_id == tenant,
                Ticket.event_id == event_id,
                Ticket.registration_id == registration_id,
                Ticket.status == "active",
            )
        )
        revoked = db.scalar(
            select(Ticket).where(
                Ticket.tenant_id == tenant,
                Ticket.event_id == event_id,
                Ticket.registration_id == registration_id,
                Ticket.status == "revoked",
            )
        )
        assert active is not None and revoked is not None
        assert service.verify_active(tenant, event_id, "v2." + "A" * 43) is None
    service.command(host, session, event_id, registration_id, "revoke")
    assert (
        service.status(host, session, event_id, registration_id)["ticket_status"] == "unavailable"
    )
    other_tenant, other_host, other_session, _other_event, _version = published(pg)
    assert other_tenant != tenant
    with pytest.raises((TicketDenied, ValueError)):
        service.status(other_host, other_session, event_id, registration_id)


def test_delivery_failure_is_visible_and_retry_reuses_intent(pg: Harness) -> None:
    tenant, _host, _session, event_id, registration_id = setup_registration(pg)

    class FailOnceTransport(MemoryTicketTransport):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def send(self, message):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls == 1:
                raise TicketDeliveryUnavailable("simulated provider outage")
            return super().send(message)

    transport = FailOnceTransport()
    service = TicketService(pg.runtime, pg.auth, TicketKeyring({1: b"s" * 32}, 1), transport)
    with Session(pg.owner) as db:
        issue_job = db.scalar(
            select(JobRecord).where(
                JobRecord.job_type == "ticket.issue",
                JobRecord.idempotency_key == registration_id,
            )
        )
        assert issue_job is not None
        db.expunge(issue_job)
    with authorized_tenant_session(pg.runtime, tenant) as db:
        service.issue_job(db, issue_job)
    with Session(pg.owner) as db:
        delivery_job = db.scalar(
            select(JobRecord).where(
                JobRecord.job_type == "ticket.deliver",
                JobRecord.tenant_id == tenant,
                JobRecord.event_id == event_id,
            )
        )
        assert delivery_job is not None
        db.expunge(delivery_job)
    assert (
        execute_job(
            pg.owner,
            pg.runtime,
            delivery_job.id,
            {"ticket.deliver": service.deliver_job},
        )
        is False
    )
    with Session(pg.owner) as db:
        failed = db.scalar(
            select(TicketDeliveryIntent).where(TicketDeliveryIntent.tenant_id == tenant)
        )
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error_code == "DELIVERY_UNAVAILABLE"
        assert failed.attempts == 1
        intent_id = failed.id
        job_state = db.get(JobRecord, delivery_job.id)
        assert job_state is not None and job_state.status == "retry_wait"
    with pg.owner.begin() as db:
        db.execute(
            text("UPDATE job_records SET next_attempt_at=now() WHERE id=:id"),
            {"id": delivery_job.id},
        )
    assert (
        execute_job(
            pg.owner,
            pg.runtime,
            delivery_job.id,
            {"ticket.deliver": service.deliver_job},
        )
        is True
    )
    with Session(pg.owner) as db:
        sent = db.scalar(select(TicketDeliveryIntent).where(TicketDeliveryIntent.id == intent_id))
        assert sent is not None
        assert sent.status == "sent"
        assert sent.attempts == 2
    assert set(transport.messages) == {intent_id}


def test_closed_event_allows_revocation_but_not_new_delivery(pg: Harness) -> None:
    tenant, host, session, event_id, registration_id = setup_registration(pg)
    service = TicketService(
        pg.runtime,
        pg.auth,
        TicketKeyring({1: b"z" * 32}, 1),
        MemoryTicketTransport(),
    )
    with Session(pg.owner) as db:
        issue_job = db.scalar(
            select(JobRecord).where(
                JobRecord.job_type == "ticket.issue",
                JobRecord.idempotency_key == registration_id,
            )
        )
        assert issue_job is not None
        db.expunge(issue_job)
    with authorized_tenant_session(pg.runtime, tenant) as db:
        service.issue_job(db, issue_job)
    with pg.owner.begin() as db:
        db.execute(
            text("UPDATE events SET status='closed' WHERE tenant_id=:tenant AND id=:event"),
            {"tenant": tenant, "event": event_id},
        )
    for action in ("resend", "reissue"):
        with pytest.raises(TicketDenied, match="unavailable for this event"):
            service.command(host, session, event_id, registration_id, action)
    assert (
        service.command(host, session, event_id, registration_id, "revoke")["ticket_status"]
        == "revoked"
    )
