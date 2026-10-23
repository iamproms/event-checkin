"""PostgreSQL-authoritative jobs. Queue messages contain a job UUID only."""

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models import JobRecord, OutboxEvent
from app.db.session import authorized_tenant_session

Handler = Callable[[Session, JobRecord], None]
DEFAULT_MAX_ATTEMPTS = 5
LEASE_SECONDS = 120
SAFE_ERROR_CODES = frozenset({"HANDLER_FAILED", "UNKNOWN_JOB_TYPE", "LEASE_EXPIRED"})


@dataclass(frozen=True)
class ClaimedJob:
    id: UUID
    tenant_id: UUID
    lease_token: UUID
    job_type: str


def enqueue_job(
    session: Session,
    *,
    tenant_id: UUID,
    job_type: str,
    idempotency_key: UUID,
    event_id: UUID | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> UUID:
    """Call inside the authoritative business transaction after authorization.

    The caller must have set transaction-scoped tenant context. The matching
    outbox row is inserted in the same transaction; caller owns commit/rollback.
    """
    if not job_type or len(job_type) > 64 or not 1 <= max_attempts <= 20:
        raise ValueError("Invalid job contract")
    candidate = uuid4()
    statement = (
        insert(JobRecord)
        .values(
            id=candidate,
            tenant_id=tenant_id,
            event_id=event_id,
            job_type=job_type,
            idempotency_key=idempotency_key,
            status="pending",
            max_attempts=max_attempts,
        )
        .on_conflict_do_nothing(constraint="uq_job_records_idempotency")
        .returning(JobRecord.id)
    )
    inserted = session.scalar(statement)
    if inserted is None:
        existing = session.scalar(
            select(JobRecord).where(
                JobRecord.tenant_id == tenant_id,
                JobRecord.job_type == job_type,
                JobRecord.idempotency_key == idempotency_key,
            )
        )
        if (
            existing is None
            or existing.event_id != event_id
            or existing.max_attempts != max_attempts
        ):
            raise ValueError("Idempotency key reused with different job parameters")
        return existing.id
    session.add(
        OutboxEvent(
            tenant_id=tenant_id,
            job_id=inserted,
            event_type="job.requested",
        )
    )
    session.flush()
    return inserted


def claim_job(operator_engine: Engine, job_id: UUID) -> ClaimedJob | None:
    """Resolve tenant from the database, never from a queue message."""
    now = datetime.now(UTC)
    with Session(operator_engine) as session, session.begin():
        job = session.scalar(
            select(JobRecord).where(JobRecord.id == job_id).with_for_update(skip_locked=True)
        )
        if job is None or job.status in {"succeeded", "dead"}:
            return None
        if job.status == "running" and (job.lease_until is None or job.lease_until > now):
            return None
        if job.status in {"pending", "retry_wait"} and job.next_attempt_at > now:
            return None
        if job.attempts >= job.max_attempts:
            job.status = "dead"
            job.lease_token = None
            job.lease_until = None
            job.finished_at = now
            job.error_code = "LEASE_EXPIRED"
            return None
        token = uuid4()
        job.status = "running"
        job.attempts += 1
        job.lease_token = token
        job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        job.started_at = job.started_at or now
        job.updated_at = now
        return ClaimedJob(job.id, job.tenant_id, token, job.job_type)


def retry_delay(attempts: int) -> timedelta:
    """Capped exponential seconds plus bounded jitter; no global RNG state."""
    cap = min(3600, 2 ** min(attempts, 12))
    return timedelta(seconds=cap + secrets.randbelow(max(1, cap // 4)))


def fail_job(operator_engine: Engine, claim: ClaimedJob, error_code: str) -> None:
    code = error_code if error_code in SAFE_ERROR_CODES else "HANDLER_FAILED"
    now = datetime.now(UTC)
    with Session(operator_engine) as session, session.begin():
        job = session.scalar(select(JobRecord).where(JobRecord.id == claim.id).with_for_update())
        if job is None or job.status != "running" or job.lease_token != claim.lease_token:
            return
        job.status = "dead" if job.attempts >= job.max_attempts else "retry_wait"
        job.lease_token = None
        job.lease_until = None
        job.error_code = code
        job.updated_at = now
        if job.status == "dead":
            job.finished_at = now
        else:
            job.next_attempt_at = now + retry_delay(job.attempts)


def execute_job(
    operator_engine: Engine,
    runtime_engine: Engine,
    job_id: UUID,
    handlers: Mapping[str, Handler],
) -> bool:
    claim = claim_job(operator_engine, job_id)
    if claim is None:
        return False
    handler = handlers.get(claim.job_type)
    if handler is None:
        fail_job(operator_engine, claim, "UNKNOWN_JOB_TYPE")
        return False
    try:
        # The runtime role has FORCE RLS. Row lock covers the effect and success
        # update in one transaction. A replacement worker cannot claim this job
        # while the first worker still owns this database transaction.
        with authorized_tenant_session(runtime_engine, claim.tenant_id) as session:
            job = session.scalar(select(JobRecord).where(JobRecord.id == job_id).with_for_update())
            if job is None or job.status != "running" or job.lease_token != claim.lease_token:
                return False
            handler(session, job)
            job.status = "succeeded"
            job.progress = 100
            job.lease_token = None
            job.lease_until = None
            job.error_code = None
            job.finished_at = datetime.now(UTC)
            job.updated_at = job.finished_at
    except Exception:
        # Exception details may include personal data; only a fixed code persists.
        fail_job(operator_engine, claim, "HANDLER_FAILED")
        return False
    return True


def due_retry_ids(operator_engine: Engine, limit: int = 100) -> list[UUID]:
    """Beat republishes due retries and expired leases; duplicates are harmless."""
    now = datetime.now(UTC)
    with Session(operator_engine) as session, session.begin():
        jobs = list(
            session.scalars(
                select(JobRecord)
                .join(OutboxEvent, OutboxEvent.job_id == JobRecord.id)
                .where(
                    or_(
                        (JobRecord.status == "retry_wait") & (JobRecord.next_attempt_at <= now),
                        (JobRecord.status == "running") & (JobRecord.lease_until <= now),
                        (JobRecord.status == "pending")
                        & (JobRecord.created_at <= now - timedelta(seconds=60))
                        & OutboxEvent.published_at.is_not(None),
                    ),
                    JobRecord.notification_after <= now,
                )
                .order_by(JobRecord.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        for job in jobs:
            job.notification_after = now + timedelta(seconds=30)
        return [job.id for job in jobs]


def inspect_dead_jobs(operator_engine: Engine, limit: int = 100) -> list[JobRecord]:
    """Operator process only; never expose this function in a public API."""
    with Session(operator_engine) as session:
        _require_recovery_role(session)
        return list(
            session.scalars(
                select(JobRecord)
                .where(JobRecord.status == "dead")
                .order_by(JobRecord.finished_at.desc())
                .limit(limit)
            )
        )


def operator_retry_dead(operator_engine: Engine, job_id: UUID) -> bool:
    """Operator-only recovery after inspecting the downstream side effect."""
    with Session(operator_engine) as session, session.begin():
        _require_recovery_role(session)
        job = session.scalar(
            select(JobRecord).where(JobRecord.id == job_id).with_for_update(skip_locked=True)
        )
        if job is None or job.status != "dead":
            return False
        job.status = "retry_wait"
        job.attempts = 0
        job.next_attempt_at = datetime.now(UTC)
        job.finished_at = None
        job.error_code = None
        job.updated_at = job.next_attempt_at
        return True


def _require_recovery_role(session: Session) -> None:
    allowed = session.scalar(
        text("SELECT pg_has_role(current_user, 'eventcheckin_job_operator', 'member')")
    )
    if allowed is not True:
        raise PermissionError("Operator role required")
