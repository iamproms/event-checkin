"""Separate dispatcher polls PostgreSQL independently of Redis availability."""

import logging
import time
from uuid import UUID

from sqlalchemy import create_engine

from app.core.config import get_settings
from app.worker.celery_app import celery_app
from app.worker.outbox import dispatch_once, publish_due_retries

logger = logging.getLogger(__name__)


def publish(job_id: UUID) -> None:
    celery_app.send_task("eventcheckin.process_job", args=[str(job_id)])


def main() -> None:
    settings = get_settings()
    if settings.dispatcher_database_url is None or settings.redis_url is None:
        raise RuntimeError("Dispatcher requires restricted dispatcher database and Redis URLs")
    engine = create_engine(settings.dispatcher_database_url.get_secret_value(), pool_pre_ping=True)
    try:
        while True:
            try:
                count = 0
                while count < 100 and dispatch_once(engine, publish):
                    count += 1
                count += publish_due_retries(engine, publish)
                if count == 0:
                    time.sleep(1)
            except Exception:
                # No exception details: drivers may include URLs or payloads.
                logger.error("Dispatcher cycle failed")
                time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
