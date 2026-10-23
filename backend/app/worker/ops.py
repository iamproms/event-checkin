"""Restricted command-line dead-letter inspection/retry; no HTTP route."""

import argparse
import json
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import create_engine

from app.core.config import get_settings
from app.worker.jobs import inspect_dead_jobs, operator_retry_dead
from app.worker.monitor import job_indicators


def main() -> None:
    parser = argparse.ArgumentParser(description="Restricted job operations")
    parser.add_argument("command", choices=("health", "dead", "retry"))
    parser.add_argument("job_id", nargs="?")
    args = parser.parse_args()
    settings = get_settings()
    if settings.jobs_operator_database_url is None:
        raise SystemExit("JOBS_OPERATOR_DATABASE_URL is required")
    engine = create_engine(
        settings.jobs_operator_database_url.get_secret_value(), pool_pre_ping=True
    )
    try:
        if args.command == "health":
            print(json.dumps(asdict(job_indicators(engine)), sort_keys=True))
        elif args.command == "dead":
            for job in inspect_dead_jobs(engine):
                print(
                    json.dumps(
                        {
                            "id": str(job.id),
                            "tenant_id": str(job.tenant_id),
                            "job_type": job.job_type,
                            "attempts": job.attempts,
                            "error_code": job.error_code,
                        }
                    )
                )
        elif args.command == "retry":
            if args.job_id is None:
                parser.error("retry requires a job ID")
            print("retried" if operator_retry_dead(engine, UUID(args.job_id)) else "not_dead")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
