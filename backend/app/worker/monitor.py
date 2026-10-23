"""Operator-only job indicators, without payloads or personal data."""

from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models import JobRecord, OutboxEvent


@dataclass(frozen=True)
class JobIndicators:
    pending: int
    running: int
    retry_wait: int
    dead: int
    unpublished: int
    expired_leases: int
    oldest_unpublished_seconds: int | None


def job_indicators(operator_engine: Engine) -> JobIndicators:
    with Session(operator_engine) as session:
        if (
            session.scalar(
                text("SELECT pg_has_role(current_user, 'eventcheckin_job_operator', 'member')")
            )
            is not True
        ):
            raise PermissionError("Operator role required")
        counts = dict(
            session.execute(select(JobRecord.status, func.count()).group_by(JobRecord.status)).all()
        )
        unpublished = (
            session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
            )
            or 0
        )
        oldest = session.scalar(
            select(func.min(OutboxEvent.created_at)).where(OutboxEvent.published_at.is_(None))
        )
        expired = (
            session.scalar(
                select(func.count())
                .select_from(JobRecord)
                .where(JobRecord.status == "running", JobRecord.lease_until < func.now())
            )
            or 0
        )
        age = None
        if oldest is not None:
            database_now = session.scalar(select(func.now()))
            if database_now is not None:
                age = max(0, int((database_now - oldest).total_seconds()))
        return JobIndicators(
            pending=counts.get("pending", 0),
            running=counts.get("running", 0),
            retry_wait=counts.get("retry_wait", 0),
            dead=counts.get("dead", 0),
            unpublished=unpublished,
            expired_leases=expired,
            oldest_unpublished_seconds=age,
        )
