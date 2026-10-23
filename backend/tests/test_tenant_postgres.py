"""Real PostgreSQL isolation tests. Never fall back to SQLite."""

import os
import secrets
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError

from app.db.session import TenantResolutionError, tenant_session_for_domain

pytestmark = pytest.mark.postgres
BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DatabaseHarness:
    owner: Engine
    runtime: Engine
    tenant_a: UUID
    tenant_b: UUID
    event_a: UUID
    event_a2: UUID
    event_b: UUID
    registration_a: UUID
    registration_b: UUID
    forbidden_database_url: str


def _migrate(url: str, revision: str) -> None:
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
    )


def _seed(owner: Engine) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID, UUID]:
    tenant_a, tenant_b = uuid4(), uuid4()
    event_a, event_a2, event_b = uuid4(), uuid4(), uuid4()
    registration_a, registration_b = uuid4(), uuid4()
    now = datetime.now(UTC)
    with owner.begin() as conn:
        for tenant, slug in [(tenant_a, "tenant-a"), (tenant_b, "tenant-b")]:
            conn.execute(
                text("INSERT INTO tenants (id,name,slug,status) VALUES (:id,:name,:slug,'active')"),
                {"id": tenant, "name": slug, "slug": slug},
            )
            conn.execute(
                text("""INSERT INTO tenant_domains
              (tenant_id,hostname,kind,verification_state,tls_state,activated_at)
              VALUES (:tenant,:hostname,'custom','verified','active',now())"""),
                {"tenant": tenant, "hostname": f"{slug}.example.test"},
            )
        for tenant, event, slug in [
            (tenant_a, event_a, "event-a"),
            (tenant_a, event_a2, "event-a2"),
            (tenant_b, event_b, "event-b"),
        ]:
            conn.execute(
                text("""INSERT INTO events
              (id,tenant_id,slug,name,starts_at,ends_at,timezone,status,pii_purge_due_at)
              VALUES (:id,:tenant,:slug,:name,:starts,:ends,'Africa/Lagos','draft',:purge)"""),
                {
                    "id": event,
                    "tenant": tenant,
                    "slug": slug,
                    "name": slug.replace("-", " ").title(),
                    "starts": now,
                    "ends": now + timedelta(hours=4),
                    "purge": now + timedelta(days=90, hours=4),
                },
            )
        for tenant, event, registration, email, phone in [
            (tenant_a, event_a, registration_a, "Ada@example.com", "+2348011111111"),
            (tenant_b, event_b, registration_b, "Bola@example.com", "+2348022222222"),
        ]:
            conn.execute(
                text("""INSERT INTO registrations
              (id,tenant_id,event_id,full_name,email,phone_e164,form_schema_version,source,status)
              VALUES (:id,:tenant,:event,'Seed Person',:email,:phone,1,'self','active')"""),
                {
                    "id": registration,
                    "tenant": tenant,
                    "event": event,
                    "email": email,
                    "phone": phone,
                },
            )
    return tenant_a, tenant_b, event_a, event_a2, event_b, registration_a, registration_b


@pytest.fixture(scope="module")
def pg() -> Iterator[DatabaseHarness]:
    raw_url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not raw_url:
        if os.environ.get("CI") == "true":
            pytest.fail("CI must provide TEST_MIGRATION_DATABASE_URL for real PostgreSQL tests")
        pytest.skip("Set TEST_MIGRATION_DATABASE_URL to a PostgreSQL migration login")
    parsed = make_url(raw_url)
    maintenance = parsed.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    suffix = secrets.token_hex(5)
    baseline_db = f"eventcheckin_m102_baseline_{suffix}"
    fresh_db = f"eventcheckin_m102_fresh_{suffix}"
    role = f"eventcheckin_m102_runtime_{suffix}"
    password = secrets.token_urlsafe(24)
    admin = psycopg.connect(maintenance, autocommit=True)
    owner: Engine | None = None
    runtime: Engine | None = None
    try:
        for name in (baseline_db, fresh_db):
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        admin.execute(
            sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(fresh_db))
        )
        baseline_url = parsed.set(database=baseline_db).render_as_string(hide_password=False)
        fresh_url = parsed.set(database=fresh_db).render_as_string(hide_password=False)
        _migrate(baseline_url, "0001_foundation")
        _migrate(baseline_url, "0002_tenant_foundation")
        _migrate(fresh_url, "0002_tenant_foundation")
        with create_engine(fresh_url).connect() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0002_tenant_foundation"
            )
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOBYPASSRLS").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        admin.execute(sql.SQL("GRANT eventcheckin_runtime TO {}").format(sql.Identifier(role)))
        admin.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(baseline_db), sql.Identifier(role)
            )
        )
        runtime_url = parsed.set(
            database=baseline_db, username=role, password=password
        ).render_as_string(hide_password=False)
        owner = create_engine(baseline_url)
        runtime = create_engine(runtime_url, pool_size=1, max_overflow=3)
        values = _seed(owner)
        forbidden_url = parsed.set(
            drivername="postgresql", database=fresh_db, username=role, password=password
        ).render_as_string(hide_password=False)
        yield DatabaseHarness(owner, runtime, *values, forbidden_url)
    finally:
        if runtime is not None:
            runtime.dispose()
        if owner is not None:
            owner.dispose()
        for name in (baseline_db, fresh_db):
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
        admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.close()


def _set_tenant(conn: Connection, tenant: UUID) -> None:
    conn.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)})


def test_runtime_role_has_no_bypass_or_global_table_access(pg: DatabaseHarness) -> None:
    with pg.runtime.connect() as conn:
        row = conn.execute(
            text("""SELECT r.rolbypassrls,
          (SELECT count(*) FROM pg_class c WHERE c.relname = 'registrations' AND c.relowner = r.oid)
          FROM pg_roles r WHERE r.rolname = current_user""")
        ).one()
        assert row == (False, 0)
    with pytest.raises(ProgrammingError):
        with pg.runtime.begin() as conn:
            conn.execute(text("SELECT * FROM tenants"))
    with pytest.raises(ProgrammingError):
        with pg.runtime.begin() as conn:
            conn.execute(text("SET ROLE eventcheckin"))
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(pg.forbidden_database_url, connect_timeout=2)
    with pg.runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            ).scalar_one()
            is False
        )


def test_all_tenant_tables_force_rls(pg: DatabaseHarness) -> None:
    expected = {
        "tenant_domains",
        "tenant_branding",
        "tenant_memberships",
        "events",
        "gates",
        "registrations",
        "tickets",
        "event_summary",
    }
    with pg.owner.connect() as conn:
        rows = conn.execute(
            text("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE n.nspname = 'public' AND c.relname = ANY(:names)"""),
            {"names": list(expected)},
        ).all()
    assert {row[0] for row in rows} == expected
    assert all(enabled and forced for _, enabled, forced in rows)


def test_tenant_cannot_read_or_mutate_another_tenant(pg: DatabaseHarness) -> None:
    with pg.runtime.begin() as conn:
        _set_tenant(conn, pg.tenant_a)
        assert (
            conn.execute(
                text("SELECT count(*) FROM registrations WHERE id = :id"), {"id": pg.registration_b}
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text("UPDATE registrations SET full_name='Changed' WHERE id=:id"),
                {"id": pg.registration_b},
            ).rowcount
            == 0
        )
        assert (
            conn.execute(
                text("DELETE FROM registrations WHERE id=:id"), {"id": pg.registration_b}
            ).rowcount
            == 0
        )
    with pytest.raises(Exception, match="row-level security"):
        with pg.runtime.begin() as conn:
            _set_tenant(conn, pg.tenant_a)
            conn.execute(
                text("""INSERT INTO registrations
              (tenant_id,event_id,full_name,email,phone_e164,form_schema_version,source,status)
              VALUES (:tenant,:event,'Wrong','wrong@example.com',
                '+2348033333333',1,'self','active')"""),
                {"tenant": pg.tenant_b, "event": pg.event_b},
            )


def test_missing_context_and_pool_reuse_fail_closed(pg: DatabaseHarness) -> None:
    with pg.runtime.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM registrations")).scalar_one() == 0
    with pg.runtime.begin() as conn:
        _set_tenant(conn, pg.tenant_a)
        assert conn.execute(text("SELECT count(*) FROM registrations")).scalar_one() >= 1
    with pg.runtime.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM registrations")).scalar_one() == 0
    with pytest.raises(DataError):
        with pg.runtime.begin() as conn:
            conn.execute(text("SELECT set_config('app.tenant_id', 'not-a-uuid', true)"))
            conn.execute(text("SELECT count(*) FROM registrations"))
    with pytest.raises(Exception, match="row-level security"):
        with pg.runtime.begin() as conn:
            conn.execute(
                text("""INSERT INTO registrations
              (tenant_id,event_id,full_name,email,phone_e164,form_schema_version,source,status)
              VALUES (:tenant,:event,'Wrong','missing@example.com',
                '+2348033333334',1,'self','active')"""),
                {"tenant": pg.tenant_a, "event": pg.event_a},
            )


def test_domain_resolution_sets_local_context(pg: DatabaseHarness) -> None:
    with tenant_session_for_domain(pg.runtime, "TENANT-A.EXAMPLE.TEST") as session:
        assert session.execute(text("SELECT count(*) FROM registrations")).scalar_one() >= 1
    with pytest.raises(TenantResolutionError):
        with tenant_session_for_domain(pg.runtime, "unknown.example.test"):
            pass
    with pg.runtime.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM registrations")).scalar_one() == 0


def test_composite_foreign_keys_reject_cross_tenant_and_event(pg: DatabaseHarness) -> None:
    with pytest.raises(IntegrityError):
        with pg.runtime.begin() as conn:
            _set_tenant(conn, pg.tenant_a)
            conn.execute(
                text(
                    """INSERT INTO gates (tenant_id,event_id,name,status)
                    VALUES (:tenant,:event,'Wrong','active')"""
                ),
                {"tenant": pg.tenant_a, "event": pg.event_b},
            )
    with pytest.raises(IntegrityError):
        with pg.runtime.begin() as conn:
            _set_tenant(conn, pg.tenant_a)
            conn.execute(
                text("""INSERT INTO tickets
              (tenant_id,event_id,registration_id,key_version,token_digest,token_ciphertext,status)
              VALUES (:tenant,:event,:registration,1,:digest,:ciphertext,'active')"""),
                {
                    "tenant": pg.tenant_a,
                    "event": pg.event_a2,
                    "registration": pg.registration_a,
                    "digest": b"x" * 32,
                    "ciphertext": b"test",
                },
            )


def _insert_registration(pg: DatabaseHarness, event: UUID, email: str, phone: str) -> None:
    with pg.runtime.begin() as conn:
        _set_tenant(conn, pg.tenant_a)
        conn.execute(
            text("""INSERT INTO registrations
          (tenant_id,event_id,full_name,email,phone_e164,form_schema_version,source,status)
          VALUES (:tenant,:event,'New Person',:email,:phone,1,'self','active')"""),
            {"tenant": pg.tenant_a, "event": event, "email": email, "phone": phone},
        )


def test_independent_email_and_phone_uniqueness(pg: DatabaseHarness) -> None:
    with pytest.raises(IntegrityError):
        _insert_registration(pg, pg.event_a, "ada@EXAMPLE.com", "+2348033333335")
    with pytest.raises(IntegrityError):
        _insert_registration(pg, pg.event_a, "another@example.com", "+2348011111111")
    _insert_registration(pg, pg.event_a2, "Ada@example.com", "+2348011111111")
    _insert_registration(pg, pg.event_a, "ada+vip@example.com", "+2348033333336")


def test_concurrent_inserts_cannot_bypass_unique_email(pg: DatabaseHarness) -> None:
    barrier = Barrier(2)

    def attempt(phone: str) -> bool:
        try:
            with pg.runtime.begin() as conn:
                _set_tenant(conn, pg.tenant_a)
                barrier.wait(timeout=5)
                conn.execute(
                    text("""INSERT INTO registrations
                  (tenant_id,event_id,full_name,email,phone_e164,form_schema_version,source,status)
                  VALUES (:tenant,:event,'Concurrent','race@example.com',
                    :phone,1,'self','active')"""),
                    {"tenant": pg.tenant_a, "event": pg.event_a, "phone": phone},
                )
            return True
        except IntegrityError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["+2348044444441", "+2348044444442"]))
    assert sorted(results) == [False, True]
