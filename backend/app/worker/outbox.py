"""At-least-once outbox publication; PostgreSQL remains authoritative."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models import OutboxEvent
from app.worker.jobs import due_retry_ids, retry_delay

Publish = Callable[[UUID], None]
OUTBOX_LEASE_SECONDS = 60


def dispatch_once(operator_engine: Engine, publish: Publish) -> bool:
    """Lease one committed row, publish its job ID, then acknowledge the row.

    A crash after publish and before acknowledgement republishes after lease
    expiry. Publish failure never deletes an outbox event or rolls back a
    previously committed business transaction.
    """
    now = datetime.now(UTC)
    with Session(operator_engine) as session, session.begin():
        event = session.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.published_at.is_(None),
                OutboxEvent.next_attempt_at <= now,
                (OutboxEvent.lease_until.is_(None)) | (OutboxEvent.lease_until <= now),
            )
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if event is None:
            return False
        event_id, job_id, token = event.id, event.job_id, uuid4()
        event.lease_token = token
        event.lease_until = now + timedelta(seconds=OUTBOX_LEASE_SECONDS)
        event.attempts += 1
    try:
        publish(job_id)
    except Exception:
        with Session(operator_engine) as session, session.begin():
            event = session.scalar(
                select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
            )
            if event is not None and event.lease_token == token and event.published_at is None:
                event.lease_token = None
                event.lease_until = None
                event.next_attempt_at = datetime.now(UTC) + retry_delay(event.attempts)
                event.last_error_code = "QUEUE_UNAVAILABLE"
        return False
    with Session(operator_engine) as session, session.begin():
        event = session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if event is not None and event.lease_token == token and event.published_at is None:
            event.published_at = datetime.now(UTC)
            event.lease_token = None
            event.lease_until = None
            event.last_error_code = None
    return True


def publish_due_retries(operator_engine: Engine, publish: Publish, limit: int = 100) -> int:
    published = 0
    for job_id in due_retry_ids(operator_engine, limit):
        try:
            publish(job_id)
        except Exception:
            # PostgreSQL remains due; a later beat will retry.
            break
        published += 1
    return published
