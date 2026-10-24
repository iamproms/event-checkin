"""M2-03 transitions, isolation, concurrency and schema on real PostgreSQL."""

import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from test_tenancy_postgres import Harness

from app.auth.security import totp_code
from app.auth.service import Forbidden
from app.db.models import Event
from app.db.session import authorized_tenant_session
from app.events.service import EventConflict, EventInvalid, EventService

pytestmark = pytest.mark.postgres
pytest_plugins = ("test_tenancy_postgres",)


def owner(pg: Harness) -> tuple[UUID, str, str]:
    suffix = secrets.token_hex(4)
    tenant, domain_id, host, proof = pg.domain.provision(pg.actor, "Event test", f"event-{suffix}")
    pg.provider.ready(host, proof)
    _, job = pg.job_for(domain_id)
    pg.worker_domain.reconcile(job, tenant)
    pg.domain.activate(pg.actor, tenant, domain_id)
    pg.domain.issue_first_owner(pg.actor, tenant, f"owner-{suffix}@example.test", pg.email)
    token = parse_qs(urlsplit(pg.email.links[-1]).fragment)["token"][0]
    _, challenge = pg.auth.accept_invitation(host, token, "event-owner-password-123")
    secret = pg.auth.enroll_totp(host, challenge)
    session, _ = pg.auth.verify_mfa(
        host, challenge, totp_code(secret, int(datetime.now(UTC).timestamp() // 30))
    )
    return tenant, host, session


def draft(service: EventService, host: str, session: str, slug: str = "conference") -> Event:
    start = datetime.now(UTC) + timedelta(days=10)
    return service.create(
        host,
        session,
        slug=slug,
        name="Àjọ Lagos",
        starts_at=start,
        ends_at=start + timedelta(hours=4),
        timezone="Africa/Lagos",
    )


def test_event_lifecycle_form_gate_retention_and_audit(pg: Harness) -> None:
    tenant, host, session = owner(pg)
    service = EventService(pg.runtime, pg.auth)
    event = draft(service, host, session)
    assert event.status == "draft" and event.pii_purge_due_at == event.ends_at + timedelta(days=90)
    later_end = event.ends_at + timedelta(hours=1)
    edited = service.edit(
        host,
        session,
        event.id,
        event.revision,
        name="Àjọ Lagos 2026",
        location="Victoria Island",
        starts_at=event.starts_at,
        ends_at=later_end,
        timezone="Africa/Lagos",
        registration_opens_at=event.starts_at - timedelta(days=3),
        registration_closes_at=event.starts_at,
        checkin_opens_at=event.starts_at,
        checkin_closes_at=later_end,
    )
    assert edited.pii_purge_due_at == later_end + timedelta(days=90)
    with pytest.raises(EventInvalid, match="Not ready"):
        service.transition(host, session, event.id, edited.revision, "published")
    form = service.set_form(
        host,
        session,
        event.id,
        edited.revision,
        {
            "fields": [
                {
                    "key": "meal",
                    "label": "Meal preference",
                    "type": "select",
                    "required": False,
                    "options": ["Vegan", "Other"],
                },
            ]
        },
    )
    assert form.form_schema_version == 2
    with pytest.raises(IntegrityError):
        with authorized_tenant_session(pg.runtime, tenant) as db:
            db.execute(
                text("""INSERT INTO registrations
                (tenant_id,event_id,full_name,email,phone_e164,form_schema_version,source,status)
                VALUES (:tenant,:event,'Fixture','form-check@example.test','+2348012345678',99,
                        'self','registered')"""),
                {"tenant": tenant, "event": event.id},
            )
    gate = service.save_gate(host, session, event.id, name="Main entrance")
    assert gate.status == "active"
    assert service.inspect_readiness(host, session, event.id) == []

    def publish() -> str:
        try:
            service.transition(host, session, event.id, form.revision, "published")
            return "published"
        except EventConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: publish(), range(2))) == ["conflict", "published"]
    published = service.get(host, session, event.id)
    assert published.status == "published"
    with pytest.raises(IntegrityError):
        with authorized_tenant_session(pg.runtime, tenant) as db:
            db.execute(
                text("UPDATE events SET form_schema='{}'::jsonb WHERE id=:id"), {"id": event.id}
            )
    with pytest.raises(EventInvalid, match="immutable"):
        service.set_form(host, session, event.id, published.revision, {"fields": []})
    with pytest.raises(EventInvalid, match="fixed"):
        service.edit(
            host,
            session,
            event.id,
            published.revision,
            name=published.name,
            location=None,
            starts_at=published.starts_at,
            ends_at=later_end + timedelta(hours=1),
            timezone=published.timezone,
            registration_opens_at=published.registration_opens_at,
            registration_closes_at=published.registration_closes_at,
            checkin_opens_at=published.checkin_opens_at,
            checkin_closes_at=published.checkin_closes_at,
        )
    closed = service.transition(host, session, event.id, published.revision, "closed")
    with pytest.raises(EventInvalid):
        service.transition(host, session, event.id, closed.revision, "published")
    with authorized_tenant_session(pg.runtime, tenant) as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM event_config_audit WHERE event_id=:id"), {"id": event.id}
            )
            >= 5
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM event_form_versions WHERE event_id=:id"),
                {"id": event.id},
            )
            == 2
        )
    with pytest.raises(ProgrammingError):
        with authorized_tenant_session(pg.runtime, tenant) as db:
            db.execute(text("DELETE FROM event_config_audit WHERE event_id=:id"), {"id": event.id})


def test_cross_tenant_gate_scope_and_concurrent_revision(pg: Harness) -> None:
    tenant_a, host_a, session_a = owner(pg)
    tenant_b, host_b, session_b = owner(pg)
    service = EventService(pg.runtime, pg.auth)
    event = draft(service, host_a, session_a, "shared")
    unassigned = draft(service, host_a, session_a, "unassigned")
    other = draft(service, host_b, session_b, "shared")
    pg.auth.issue_invitation(
        host_a, session_a, f"organizer-{uuid4()}@example.test", "organizer", event.id, None
    )
    organizer_token = parse_qs(urlsplit(pg.email.links[-1]).fragment)["token"][0]
    _, organizer_challenge = pg.auth.accept_invitation(
        host_a, organizer_token, "organizer-password-1234"
    )
    organizer_secret = pg.auth.enroll_totp(host_a, organizer_challenge)
    organizer_session, _ = pg.auth.verify_mfa(
        host_a,
        organizer_challenge,
        totp_code(organizer_secret, int(datetime.now(UTC).timestamp() // 30)),
    )
    assert [row.id for row in service.list_events(host_a, organizer_session)] == [event.id]
    with pytest.raises(Forbidden):
        draft(service, host_a, organizer_session, "unauthorized-create")
    assert unassigned.id != event.id
    with pytest.raises(EventInvalid):
        service.get(host_b, session_b, event.id)
    with pytest.raises(EventInvalid):
        service.get(host_a, session_a, other.id)
    with pytest.raises((EventInvalid, Forbidden)):
        service.save_gate(host_b, session_b, event.id, name="Wrong")
    gate = service.save_gate(host_a, session_a, event.id, name="Same")
    assert gate.event_id == event.id
    with pytest.raises(IntegrityError):
        service.save_gate(host_a, session_a, event.id, name="Same")
    with pytest.raises(IntegrityError):
        with authorized_tenant_session(pg.runtime, tenant_a) as db:
            db.execute(
                text("""INSERT INTO gates(tenant_id,event_id,name,status)
                VALUES (:tenant,:event,'Cross','active')"""),
                {"tenant": tenant_a, "event": other.id},
            )
    assert tenant_a != tenant_b
    with authorized_tenant_session(pg.runtime, tenant_b) as db:
        assert (
            db.scalar(
                text("SELECT count(*) FROM event_form_versions WHERE event_id=:id"),
                {"id": event.id},
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM event_config_audit WHERE event_id=:id"), {"id": event.id}
            )
            == 0
        )
    with pytest.raises(IntegrityError):
        with authorized_tenant_session(pg.runtime, tenant_b) as db:
            db.execute(
                text("""INSERT INTO event_form_versions(tenant_id,event_id,version,schema)
                VALUES (:tenant,:event,77,'{}'::jsonb)"""),
                {"tenant": tenant_b, "event": event.id},
            )

    def rename(name: str) -> str:
        try:
            service.edit(
                host_a,
                session_a,
                event.id,
                event.revision,
                name=name,
                location=None,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                timezone=event.timezone,
                registration_opens_at=None,
                registration_closes_at=None,
                checkin_opens_at=None,
                checkin_closes_at=None,
            )
            return "saved"
        except EventConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(rename, ("Ada", "Chinwe"))) == ["conflict", "saved"]
    with authorized_tenant_session(pg.runtime, tenant_b) as db:
        assert db.scalar(text("SELECT count(*) FROM events WHERE id=:id"), {"id": event.id}) == 0


def test_cancellation_terminal_and_scanner_denied(pg: Harness) -> None:
    tenant, host, session = owner(pg)
    service = EventService(pg.runtime, pg.auth)
    event = draft(service, host, session, "cancelled")
    gate = service.save_gate(host, session, event.id, name="Scanner gate")
    pg.auth.issue_invitation(
        host, session, f"scanner-{uuid4()}@example.test", "gate_scanner", event.id, gate.id
    )
    invitation = parse_qs(urlsplit(pg.email.links[-1]).fragment)["token"][0]
    state, scanner_session = pg.auth.accept_invitation(host, invitation, "scanner-password-1234")
    assert state == "session"
    with pytest.raises(Forbidden):
        service.get(host, scanner_session, event.id)
    cancelled = service.transition(host, session, event.id, event.revision, "cancelled")
    with pytest.raises(EventInvalid):
        service.transition(host, session, event.id, cancelled.revision, "published")
    with pytest.raises(IntegrityError):
        with authorized_tenant_session(pg.runtime, tenant) as db:
            db.execute(text("UPDATE events SET status='draft' WHERE id=:id"), {"id": event.id})
    with pytest.raises(Forbidden):
        pg.auth.issue_invitation(
            host, session, f"scanner-{uuid4()}@example.test", "gate_scanner", event.id, gate.id
        )
    assert pg.auth.authorize(host, session, "gate.manage", event.id, gate.id) == tenant
