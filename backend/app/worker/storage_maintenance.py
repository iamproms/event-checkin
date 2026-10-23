"""Local/test-only lifecycle sweep for approved synthetic artifacts."""

import logging
import time

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import Environment, Settings, get_settings
from app.db.models import PrivateObject
from app.db.session import authorized_tenant_session
from app.worker.storage import InternalTestArtifactService, PrivateStorage, s3_storage

logger = logging.getLogger(__name__)


def sweep_expired(
    settings: Settings, operator_engine: Engine, runtime_engine: Engine, storage: PrivateStorage
) -> int:
    if settings.app_env not in {Environment.LOCAL, Environment.TEST}:
        raise PermissionError("Test artifact sweeper is disabled")
    with Session(operator_engine) as session:
        allowed = session.scalar(
            text("SELECT pg_has_role(current_user, 'eventcheckin_job_operator', 'member')")
        )
        if allowed is not True:
            raise PermissionError("Operator role required")
        tenants = list(
            session.scalars(
                select(PrivateObject.tenant_id)
                .where(
                    PrivateObject.purpose == "internal_test_artifact",
                    PrivateObject.status != "deleted",
                    PrivateObject.expires_at <= func.now(),
                )
                .distinct()
                .limit(100)
            )
        )
    service = InternalTestArtifactService(settings, storage)
    deleted = 0
    for tenant_id in tenants:
        with authorized_tenant_session(runtime_engine, tenant_id) as session:
            deleted += service.cleanup_expired(session)
    return deleted


def main() -> None:
    settings = get_settings()
    if settings.app_env not in {Environment.LOCAL, Environment.TEST}:
        raise SystemExit("Test artifact sweeper is disabled")
    if settings.jobs_operator_database_url is None:
        raise SystemExit("JOBS_OPERATOR_DATABASE_URL is required")
    operator = create_engine(
        settings.jobs_operator_database_url.get_secret_value(), pool_pre_ping=True
    )
    runtime = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
    storage = s3_storage(settings)
    try:
        while True:
            try:
                sweep_expired(settings, operator, runtime, storage)
            except Exception:
                # Storage/driver exceptions may contain signed URLs: never log them.
                logger.error("Test artifact cleanup cycle failed")
            time.sleep(60)
    finally:
        operator.dispose()
        runtime.dispose()


if __name__ == "__main__":
    main()
