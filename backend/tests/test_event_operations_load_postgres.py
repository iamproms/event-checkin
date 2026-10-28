"""Opt-in, isolated 5,000-row import rehearsal without sending email."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_events_postgres import owner
from test_registration_postgres import seed_notice
from test_tenancy_postgres import Harness

from app.db.models import JobRecord
from app.db.session import authorized_tenant_session
from app.events.service import EventService
from app.operations.service import EventOperationsService
from app.tickets.crypto import TicketKeyring
from app.tickets.email import MemoryTicketTransport
from app.tickets.service import TicketService

pytestmark = pytest.mark.postgres
pytest_plugins = ("test_tenancy_postgres",)


@pytest.mark.skipif(
    os.environ.get("RUN_EVENT_LOAD_TEST") != "1",
    reason="Set RUN_EVENT_LOAD_TEST=1 for the 5,000-row database rehearsal",
)
def test_five_thousand_email_only_rows_import_then_queue_ticket_issuance(pg: Harness) -> None:
    tenant, host, session = owner(pg)
    events = EventService(pg.runtime, pg.auth)
    start = datetime.now(UTC) + timedelta(days=2)
    event = events.create(
        host,
        session,
        name="Import rehearsal",
        starts_at=start,
        ends_at=start + timedelta(hours=4),
        timezone="Africa/Lagos",
        registration_mode="import_only",
    )
    configured = events.edit(
        host,
        session,
        event.id,
        event.revision,
        name=event.name,
        location="Rehearsal venue",
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        timezone=event.timezone,
        registration_opens_at=None,
        registration_closes_at=None,
        checkin_opens_at=event.starts_at,
        checkin_closes_at=event.ends_at,
    )
    events.save_gate(host, session, event.id, name="Main entrance")
    events.transition(host, session, event.id, configured.revision, "published")
    event_id = event.id
    seed_notice(pg, tenant)
    operations = EventOperationsService(pg.runtime, pg.auth)
    lines = ["email"]
    lines.extend(f"attendee-{index:05d}@example.test" for index in range(1, 5001))
    preview = operations.preview_import(
        host, session, event_id, "synthetic-5000.csv", ("\n".join(lines) + "\n").encode()
    )
    import_id = UUID(str(preview["import_id"]))
    mapping = {"email": "email"}
    validated = operations.validate_import(
        host, session, event_id, import_id, mapping
    )
    assert (validated["valid_count"], validated["invalid_count"], validated["duplicate_count"]) == (
        5000,
        0,
        0,
    )
    operations.commit_import(host, session, event_id, import_id, True)
    processed_chunks = 0
    while True:
        with Session(pg.owner) as owner_db:
            job_id = owner_db.scalar(
                text("SELECT current_job_id FROM participant_imports WHERE id=:import_id"),
                {"import_id": import_id},
            )
            if job_id is None:
                break
            job = owner_db.get(JobRecord, job_id)
            assert job is not None
            owner_db.expunge(job)
        with authorized_tenant_session(pg.runtime, tenant) as db:
            operations.process_import_job(db, job)
        processed_chunks += 1
        assert processed_chunks <= 25
    assert processed_chunks == 25
    assert operations.import_status(host, session, event_id, import_id)["status"] == "completed"
    with pg.owner.connect() as owner_db:
        assert (
            owner_db.scalar(
                text("SELECT count(*) FROM registrations WHERE event_id=:event"),
                {"event": event_id},
            )
            == 5000
        )
        assert (
            owner_db.scalar(
                text(
                    "SELECT count(*) FROM job_records "
                    "WHERE event_id=:event AND job_type='ticket.issue'"
                ),
                {"event": event_id},
            )
            == 0
        )
    tickets = TicketService(
        pg.runtime, pg.auth, TicketKeyring({1: b"i" * 32}, 1), MemoryTicketTransport()
    )
    assert tickets.issue_bulk(host, session, event_id)["eligible"] == 5000
    assert tickets.issue_bulk(host, session, event_id)["eligible"] == 5000
    with pg.owner.connect() as owner_db:
        assert (
            owner_db.scalar(
                text(
                    "SELECT count(*) FROM job_records "
                    "WHERE event_id=:event AND job_type='ticket.issue'"
                ),
                {"event": event_id},
            )
            == 5000
        )
