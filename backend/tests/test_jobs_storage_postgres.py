"""M1-04 security/recovery tests. These require isolated real PostgreSQL."""

import os
import secrets
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_tenant_postgres import _migrate

from app.core.config import Settings
from app.db.models import JobRecord, OutboxEvent
from app.db.session import authorized_tenant_session
from app.worker.jobs import enqueue_job, execute_job, inspect_dead_jobs, operator_retry_dead
from app.worker.outbox import dispatch_once, publish_due_retries
from app.worker.storage import InternalTestArtifactService, StorageDenied
from app.worker.storage_maintenance import sweep_expired

pytestmark = pytest.mark.postgres


@dataclass(frozen=True)
class JobDatabase:
    owner: Engine
    runtime: Engine
    operator: Engine
    dispatcher: Engine
    recovery: Engine
    tenant_a: UUID
    tenant_b: UUID
    event_a: UUID


@pytest.fixture(scope="module")
def db() -> Iterator[JobDatabase]:
    raw = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not raw:
        if os.environ.get("CI") == "true":
            pytest.fail("CI requires TEST_MIGRATION_DATABASE_URL")
        pytest.skip("Set TEST_MIGRATION_DATABASE_URL for real PostgreSQL tests")
    parsed = make_url(raw)
    suffix = secrets.token_hex(5)
    database = f"eventcheckin_m104_{suffix}"
    runtime_role = f"eventcheckin_m104_runtime_{suffix}"
    jobs_role = f"eventcheckin_m104_jobs_{suffix}"
    dispatcher_role = f"eventcheckin_m104_dispatcher_{suffix}"
    recovery_role = f"eventcheckin_m104_operator_{suffix}"
    runtime_password, jobs_password, dispatcher_password, recovery_password = (
        secrets.token_urlsafe(24),
        secrets.token_urlsafe(24),
        secrets.token_urlsafe(24),
        secrets.token_urlsafe(24),
    )
    maintenance = parsed.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    admin = psycopg.connect(maintenance, autocommit=True)
    owner: Engine | None = None
    runtime: Engine | None = None
    operator: Engine | None = None
    dispatcher: Engine | None = None
    recovery: Engine | None = None
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        url = parsed.set(database=database).render_as_string(hide_password=False)
        _migrate(url, "0004_auth_session_invalidation")
        _migrate(url, "head")
        _migrate(url, "0004_auth_session_invalidation", direction="downgrade")
        _migrate(url, "head")
        owner = create_engine(url)
        with owner.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0007_event_configuration"
            )
            for table in ("job_records", "outbox_events", "private_objects"):
                assert conn.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity "
                        "FROM pg_class WHERE relname=:name"
                    ),
                    {"name": table},
                ).one() == (True, True)
        for role, password, group in (
            (runtime_role, runtime_password, "eventcheckin_runtime"),
            (jobs_role, jobs_password, "eventcheckin_jobs"),
            (dispatcher_role, dispatcher_password, "eventcheckin_dispatcher"),
            (recovery_role, recovery_password, "eventcheckin_job_operator"),
        ):
            admin.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOBYPASSRLS").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            admin.execute(
                sql.SQL("GRANT {} TO {}").format(sql.Identifier(group), sql.Identifier(role))
            )
            admin.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database), sql.Identifier(role)
                )
            )
        runtime_url = parsed.set(
            database=database, username=runtime_role, password=runtime_password
        ).render_as_string(hide_password=False)
        jobs_url = parsed.set(
            database=database, username=jobs_role, password=jobs_password
        ).render_as_string(hide_password=False)
        dispatcher_url = parsed.set(
            database=database, username=dispatcher_role, password=dispatcher_password
        ).render_as_string(hide_password=False)
        recovery_url = parsed.set(
            database=database, username=recovery_role, password=recovery_password
        ).render_as_string(hide_password=False)
        runtime = create_engine(runtime_url, pool_size=1, max_overflow=3)
        operator = create_engine(jobs_url, pool_size=1, max_overflow=3)
        dispatcher = create_engine(dispatcher_url, pool_size=1, max_overflow=3)
        recovery = create_engine(recovery_url, pool_size=1, max_overflow=3)
        tenant_a, tenant_b, event_a = uuid4(), uuid4(), uuid4()
        now = datetime.now(UTC)
        with owner.begin() as conn:
            for tenant, slug, name in (
                (tenant_a, "job-a", "Job tenant A"),
                (tenant_b, "job-b", "Job tenant B"),
            ):
                conn.execute(
                    text(
                        "INSERT INTO tenants (id,name,slug,status) "
                        "VALUES (:id,:name,:slug,'active')"
                    ),
                    {"id": tenant, "name": name, "slug": slug},
                )
            conn.execute(
                text("""INSERT INTO events
                    (id,tenant_id,slug,name,starts_at,ends_at,timezone,status,pii_purge_due_at)
                    VALUES (:id,:tenant,'job-event','Job event',:starts,:ends,'Africa/Lagos',
                    'draft',:purge)"""),
                {
                    "id": event_a,
                    "tenant": tenant_a,
                    "starts": now,
                    "ends": now + timedelta(hours=4),
                    "purge": now + timedelta(days=90, hours=4),
                },
            )
            conn.execute(
                text("INSERT INTO event_summary (tenant_id,event_id) VALUES (:tenant,:event)"),
                {"tenant": tenant_a, "event": event_a},
            )
        yield JobDatabase(
            owner, runtime, operator, dispatcher, recovery, tenant_a, tenant_b, event_a
        )
    finally:
        for engine in (recovery, dispatcher, operator, runtime, owner):
            if engine is not None:
                engine.dispose()
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database))
        )
        for role in (recovery_role, dispatcher_role, jobs_role, runtime_role):
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.close()


@pytest.fixture(autouse=True)
def isolate_job_cases(db: JobDatabase) -> Iterator[None]:
    """Keep the module's temporary database while isolating dispatcher queues per case."""
    yield
    with db.owner.begin() as conn:
        conn.execute(text("DELETE FROM outbox_events"))
        conn.execute(text("DELETE FROM job_records"))
        conn.execute(text("DELETE FROM private_objects"))
        conn.execute(
            text(
                "UPDATE event_summary SET registered_count=0 "
                "WHERE tenant_id=:tenant AND event_id=:event"
            ),
            {"tenant": db.tenant_a, "event": db.event_a},
        )


def _enqueue(db: JobDatabase, key: UUID | None = None, max_attempts: int = 5) -> UUID:
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        return enqueue_job(
            session,
            tenant_id=db.tenant_a,
            event_id=db.event_a,
            job_type="internal_test_noop",
            idempotency_key=key or uuid4(),
            max_attempts=max_attempts,
        )


def test_atomic_commit_rollback_and_idempotency(db: JobDatabase) -> None:
    key = uuid4()
    with pytest.raises(RuntimeError), authorized_tenant_session(db.runtime, db.tenant_a) as session:
        session.execute(
            text(
                "UPDATE event_summary SET registered_count=registered_count+1 "
                "WHERE tenant_id=:tenant AND event_id=:event"
            ),
            {"tenant": db.tenant_a, "event": db.event_a},
        )
        enqueue_job(
            session,
            tenant_id=db.tenant_a,
            event_id=db.event_a,
            job_type="internal_test_noop",
            idempotency_key=key,
        )
        raise RuntimeError("rollback")
    with db.owner.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM job_records WHERE idempotency_key=:key"), {"key": key}
            )
            == 0
        )
        assert (
            conn.scalar(
                text("SELECT registered_count FROM event_summary WHERE event_id=:id"),
                {"id": db.event_a},
            )
            == 0
        )
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        session.execute(
            text(
                "UPDATE event_summary SET registered_count=registered_count+1 "
                "WHERE tenant_id=:tenant AND event_id=:event"
            ),
            {"tenant": db.tenant_a, "event": db.event_a},
        )
        first = enqueue_job(
            session,
            tenant_id=db.tenant_a,
            event_id=db.event_a,
            job_type="internal_test_noop",
            idempotency_key=key,
        )
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        assert (
            enqueue_job(
                session,
                tenant_id=db.tenant_a,
                event_id=db.event_a,
                job_type="internal_test_noop",
                idempotency_key=key,
            )
            == first
        )
    with db.owner.connect() as conn:
        assert (
            conn.scalar(text("SELECT count(*) FROM outbox_events WHERE job_id=:id"), {"id": first})
            == 1
        )


def test_direct_job_insert_without_outbox_is_rejected(db: JobDatabase) -> None:
    candidate = uuid4()
    with (
        pytest.raises(IntegrityError),
        authorized_tenant_session(db.runtime, db.tenant_a) as session,
    ):
        session.add(
            JobRecord(
                id=candidate,
                tenant_id=db.tenant_a,
                event_id=db.event_a,
                job_type="internal_test_noop",
                idempotency_key=uuid4(),
                status="pending",
                max_attempts=5,
            )
        )
        session.flush()
    with db.owner.connect() as conn:
        assert (
            conn.scalar(text("SELECT count(*) FROM job_records WHERE id=:id"), {"id": candidate})
            == 0
        )


def test_dispatch_crash_restart_queue_outage_and_duplicate_worker(db: JobDatabase) -> None:
    job_id = _enqueue(db)
    delivered: list[UUID] = []
    with db.owner.connect() as conn:
        before = conn.scalar(
            text("SELECT registered_count FROM event_summary WHERE event_id=:id"),
            {"id": db.event_a},
        )

    def uncertain_publish(value: UUID) -> None:
        delivered.append(value)
        raise ConnectionError("simulated broker failure after publish")

    assert dispatch_once(db.dispatcher, uncertain_publish) is False
    with db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE outbox_events SET next_attempt_at=now()-interval '1 second' "
                "WHERE job_id=:id"
            ),
            {"id": job_id},
        )
    assert dispatch_once(db.dispatcher, delivered.append) is True
    assert delivered == [job_id, job_id]

    def effect(session: Session, job: JobRecord) -> None:
        session.execute(
            text(
                "UPDATE event_summary SET registered_count=registered_count+1 "
                "WHERE tenant_id=:tenant AND event_id=:event"
            ),
            {"tenant": job.tenant_id, "event": job.event_id},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: execute_job(
                    db.operator, db.runtime, job_id, {"internal_test_noop": effect}
                ),
                range(2),
            )
        )
    assert results.count(True) == 1
    assert results.count(False) == 1
    with db.owner.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT registered_count FROM event_summary WHERE event_id=:id"),
                {"id": db.event_a},
            )
            == before + 1
        )
        assert (
            conn.scalar(text("SELECT status FROM job_records WHERE id=:id"), {"id": job_id})
            == "succeeded"
        )


def test_published_but_lost_broker_message_is_recovered(db: JobDatabase) -> None:
    job_id = _enqueue(db)
    assert dispatch_once(db.dispatcher, lambda value: None) is True
    with db.owner.begin() as conn:
        conn.execute(
            text("UPDATE job_records SET created_at=now()-interval '61 seconds' WHERE id=:id"),
            {"id": job_id},
        )
    republished: list[UUID] = []
    assert publish_due_retries(db.dispatcher, republished.append) >= 1
    assert job_id in republished
    assert publish_due_retries(db.dispatcher, republished.append) == 0
    assert (
        execute_job(
            db.operator, db.runtime, job_id, {"internal_test_noop": lambda session, job: None}
        )
        is True
    )


def test_expired_lease_retry_dead_and_operator_recovery(db: JobDatabase) -> None:
    job_id = _enqueue(db, max_attempts=2)
    with db.owner.begin() as conn:
        conn.execute(
            text("""UPDATE job_records SET status='running',attempts=1,
                   lease_token=gen_random_uuid(),lease_until=now()-interval '1 second'
                   WHERE id=:id"""),
            {"id": job_id},
        )
    assert (
        execute_job(
            db.operator, db.runtime, job_id, {"internal_test_noop": lambda session, job: None}
        )
        is True
    )
    failing = _enqueue(db, max_attempts=2)

    def fail(session: Session, job: JobRecord) -> None:
        raise RuntimeError("sensitive detail must never persist")

    assert execute_job(db.operator, db.runtime, failing, {"internal_test_noop": fail}) is False
    with db.owner.begin() as conn:
        assert (
            conn.scalar(text("SELECT status FROM job_records WHERE id=:id"), {"id": failing})
            == "retry_wait"
        )
        conn.execute(
            text("UPDATE job_records SET next_attempt_at=now()-interval '1 second' WHERE id=:id"),
            {"id": failing},
        )
    assert publish_due_retries(db.dispatcher, lambda value: None) >= 1
    assert publish_due_retries(db.dispatcher, lambda value: None) == 0
    assert execute_job(db.operator, db.runtime, failing, {"internal_test_noop": fail}) is False
    with pytest.raises(PermissionError):
        inspect_dead_jobs(db.operator)
    assert failing in {job.id for job in inspect_dead_jobs(db.recovery)}
    with db.owner.connect() as conn:
        assert (
            conn.scalar(text("SELECT error_code FROM job_records WHERE id=:id"), {"id": failing})
            == "HANDLER_FAILED"
        )
    with pytest.raises(PermissionError):
        operator_retry_dead(db.operator, failing)
    assert operator_retry_dead(db.recovery, failing) is True


def test_tenant_substitution_rls_and_least_privilege(db: JobDatabase) -> None:
    job_id = _enqueue(db)
    with authorized_tenant_session(db.runtime, db.tenant_b) as session:
        assert session.scalar(select(JobRecord).where(JobRecord.id == job_id)) is None
        assert session.scalar(select(OutboxEvent).where(OutboxEvent.job_id == job_id)) is None
        assert (
            session.execute(
                text("UPDATE job_records SET status='dead' WHERE id=:id"), {"id": job_id}
            ).rowcount
            == 0
        )
    with Session(db.runtime) as session:
        assert session.scalar(select(JobRecord).where(JobRecord.id == job_id)) is None
    with db.operator.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(text("SELECT * FROM registrations"))
    with db.operator.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(
                text("UPDATE outbox_events SET published_at=now() WHERE job_id=:id"),
                {"id": job_id},
            )
    with db.dispatcher.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(text("SELECT * FROM registrations"))
    with db.operator.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(
                text("UPDATE job_records SET tenant_id=:tenant WHERE id=:id"),
                {"tenant": db.tenant_b, "id": job_id},
            )
    with db.owner.connect() as conn:
        assert (
            conn.scalar(text("SELECT status FROM job_records WHERE id=:id"), {"id": job_id})
            == "pending"
        )


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[str, int]] = {}

    def upload_post(
        self, key: str, mime_type: str, max_bytes: int, lifetime_seconds: int
    ) -> tuple[str, dict[str, str]]:
        return f"https://private.example.test/{key}?expires={lifetime_seconds}", {}

    def download_url(self, key: str, lifetime_seconds: int) -> str:
        return f"https://private.example.test/{key}?expires={lifetime_seconds}"

    def metadata(self, key: str) -> tuple[str, int, str]:
        mime_type, size = self.objects[key]
        return mime_type, size, '"synthetic-etag"'

    def promote(self, source_key: str, final_key: str, etag: str) -> None:
        assert etag == '"synthetic-etag"'
        self.objects[final_key] = self.objects[source_key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


def test_private_object_authorization_expiry_and_cleanup(db: JobDatabase) -> None:
    storage = FakeStorage()
    service = InternalTestArtifactService(
        Settings(app_env="test", database_url="postgresql+psycopg://x:y@localhost/x"), storage
    )
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        grant = service.request_upload(session, db.tenant_a, "text/plain", 100)
    with authorized_tenant_session(db.runtime, db.tenant_b) as session:
        with pytest.raises(StorageDenied):
            service.download(session, grant.object_id)
    with db.owner.connect() as conn:
        key = conn.scalar(
            text("SELECT object_key FROM private_objects WHERE id=:id"), {"id": grant.object_id}
        )
    storage.objects[key] = ("text/plain", 10)
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        assert service.complete_upload(session, grant.object_id)
        assert "expires=" in service.download(session, grant.object_id)
    with db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE private_objects SET created_at=now()-interval '23 hours', "
                "expires_at=now()-interval '1 second' "
                "WHERE id=:id"
            ),
            {"id": grant.object_id},
        )
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        with pytest.raises(StorageDenied):
            service.download(session, grant.object_id)
    assert sweep_expired(service.settings, db.recovery, db.runtime, storage) >= 1
    assert key not in storage.objects
    assert not storage.objects


def test_test_artifacts_disabled_in_production(db: JobDatabase) -> None:
    service = InternalTestArtifactService(
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://x:y@db.example.test/x?sslmode=verify-full",
        ),
        FakeStorage(),
    )
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        with pytest.raises(StorageDenied):
            service.request_upload(session, db.tenant_a, "text/plain", 10)


def test_real_redis_outage_and_recovery(db: JobDatabase) -> None:
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        if os.environ.get("CI") == "true":
            pytest.fail("CI requires TEST_REDIS_URL")
        pytest.skip("Set TEST_REDIS_URL for Redis integration")
    redis = pytest.importorskip("redis")
    celery = pytest.importorskip("celery")
    job_id = _enqueue(db)
    dead = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)

    def unavailable(value: UUID) -> None:
        dead.ping()

    assert dispatch_once(db.dispatcher, unavailable) is False
    with db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE outbox_events SET next_attempt_at=now()-interval '1 second' "
                "WHERE job_id=:id"
            ),
            {"id": job_id},
        )
    client = redis.Redis.from_url(url)
    assert client.ping()
    app = celery.Celery("m104_test", broker=url)
    app.conf.update(task_publish_retry=False, task_default_queue="m104-test")
    try:
        assert (
            dispatch_once(
                db.dispatcher,
                lambda value: app.send_task("eventcheckin.process_job", args=[str(value)]),
            )
            is True
        )
        assert client.llen("m104-test") >= 1
    finally:
        app.close()


def test_real_private_object_storage(db: JobDatabase) -> None:
    endpoint = os.environ.get("TEST_S3_ENDPOINT")
    bucket = os.environ.get("TEST_S3_BUCKET")
    access = os.environ.get("TEST_S3_ACCESS_KEY")
    secret = os.environ.get("TEST_S3_SECRET_KEY")
    if not all((endpoint, bucket, access, secret)):
        if os.environ.get("CI") == "true":
            pytest.fail("CI requires test object storage settings")
        pytest.skip("Set TEST_S3_* for real private object integration")
    import httpx

    from app.worker.storage import s3_storage

    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://x:y@localhost/x",
        storage_endpoint_url=endpoint,
        storage_bucket=bucket,
        storage_access_key=access,
        storage_secret_key=secret,
        download_url_seconds=1,
    )
    storage = s3_storage(settings)
    service = InternalTestArtifactService(settings, storage)
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        grant = service.request_upload(session, db.tenant_a, "text/plain", 1024)
    response = httpx.post(
        grant.url,
        data=grant.fields,
        files={"file": ("synthetic.txt", b"synthetic test data", "text/plain")},
        timeout=10,
    )
    assert response.status_code in {200, 204}
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        assert service.complete_upload(session, grant.object_id)
        download = service.download(session, grant.object_id)
    assert httpx.get(download, timeout=10).content == b"synthetic test data"
    with db.owner.connect() as conn:
        final_key = conn.scalar(
            text("SELECT object_key FROM private_objects WHERE id=:id"),
            {"id": grant.object_id},
        )
    assert httpx.get(f"{endpoint}/{bucket}/{final_key}", timeout=10).status_code in {401, 403}
    time.sleep(2)
    assert httpx.get(download, timeout=10).status_code in {401, 403}
    with authorized_tenant_session(db.runtime, db.tenant_b) as session:
        with pytest.raises(StorageDenied):
            service.download(session, grant.object_id)
    with db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE private_objects SET created_at=now()-interval '23 hours', "
                "expires_at=now()-interval '1 second' "
                "WHERE id=:id"
            ),
            {"id": grant.object_id},
        )
    with authorized_tenant_session(db.runtime, db.tenant_a) as session:
        with pytest.raises(StorageDenied):
            service.download(session, grant.object_id)
        assert service.cleanup_expired(session) >= 1
