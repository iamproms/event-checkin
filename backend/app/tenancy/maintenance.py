"""PostgreSQL-driven domain reconciliation scheduler."""

import argparse
import time

from sqlalchemy import create_engine

from app.core.config import get_settings
from app.tenancy.domains import schedule_due_reconciliations


def main() -> None:
    parser = argparse.ArgumentParser(description="Schedule due web-domain checks")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if settings.domain_scheduler_database_url is None:
        parser.error("DOMAIN_SCHEDULER_DATABASE_URL is required")
    engine = create_engine(
        settings.domain_scheduler_database_url.get_secret_value(), pool_pre_ping=True
    )
    try:
        while True:
            schedule_due_reconciliations(engine)
            if args.once:
                break
            time.sleep(60)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
