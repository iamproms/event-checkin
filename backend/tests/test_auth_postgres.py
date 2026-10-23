"""M1-03 integration checks. This module requires a real isolated PostgreSQL database."""

import base64
import hashlib
import os
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, ProgrammingError
from test_tenant_postgres import _migrate

from app.auth.corpus import CompromisedPasswordCorpus
from app.auth.email import DisabledEmailDelivery
from app.auth.security import hash_password, new_token, token_digest, totp_code
from app.auth.service import AuthDenied, AuthService
from app.core.config import Settings
from app.db.session import authorized_tenant_session

pytestmark = pytest.mark.postgres


@dataclass(frozen=True)
class AuthDatabase:
    owner: Engine
    identity: Engine
    runtime: Engine
    tenant_a: UUID
    tenant_b: UUID
    user: UUID
    settings: Settings


@pytest.fixture(scope="module")
def auth_db() -> Iterator[AuthDatabase]:
    raw_url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not raw_url:
        if os.environ.get("CI") == "true":
            pytest.fail("CI requires TEST_MIGRATION_DATABASE_URL for real PostgreSQL tests")
        pytest.skip("Set TEST_MIGRATION_DATABASE_URL for real PostgreSQL tests")
    parsed = make_url(raw_url)
    suffix = secrets.token_hex(5)
    database = f"eventcheckin_m103_{suffix}"
    fresh_database = f"eventcheckin_m103_fresh_{suffix}"
    identity_role = f"eventcheckin_identity_test_{suffix}"
    runtime_role = f"eventcheckin_runtime_test_{suffix}"
    identity_password, runtime_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    maintenance = parsed.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    admin = psycopg.connect(maintenance, autocommit=True)
    owner: Engine | None = None
    identity: Engine | None = None
    runtime: Engine | None = None
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(fresh_database)))
        url = parsed.set(database=database).render_as_string(hide_password=False)
        fresh_url = parsed.set(database=fresh_database).render_as_string(hide_password=False)
        _migrate(url, "0002_tenant_foundation")
        _migrate(url, "head")
        _migrate(fresh_url, "head")
        _migrate(url, "0002_tenant_foundation")
        _migrate(url, "head")
        owner = create_engine(url)
        with owner.connect() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0004_auth_session_invalidation"
            )
            for table in ("staff_invitations", "event_assignments"):
                state = conn.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                        "WHERE relname=:name"
                    ),
                    {"name": table},
                ).one()
                assert state == (True, True)
        for role, password, group in (
            (identity_role, identity_password, "eventcheckin_identity"),
            (runtime_role, runtime_password, "eventcheckin_runtime"),
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
        identity_url = parsed.set(
            database=database, username=identity_role, password=identity_password
        ).render_as_string(hide_password=False)
        runtime_url = parsed.set(
            database=database, username=runtime_role, password=runtime_password
        ).render_as_string(hide_password=False)
        identity = create_engine(identity_url, pool_size=1, max_overflow=0)
        runtime = create_engine(runtime_url, pool_size=1, max_overflow=0)
        tenant_a, tenant_b, user = uuid4(), uuid4(), uuid4()
        with owner.begin() as conn:
            for tenant, name in ((tenant_a, "auth-a"), (tenant_b, "auth-b")):
                conn.execute(
                    text(
                        "INSERT INTO tenants (id,name,slug,status) "
                        "VALUES (:id,:name,:slug,'active')"
                    ),
                    {"id": tenant, "name": name, "slug": name},
                )
                conn.execute(
                    text(
                        "INSERT INTO tenant_domains "
                        "(tenant_id,hostname,kind,verification_state,tls_state,activated_at) "
                        "VALUES (:tenant,:host,'custom','verified','active',now())"
                    ),
                    {"tenant": tenant, "host": f"{name}.example.test"},
                )
            conn.execute(
                text(
                    "INSERT INTO users (id,email,display_name,status) "
                    "VALUES (:id,'staff@example.test','Staff Member','active')"
                ),
                {"id": user},
            )
            conn.execute(
                text("INSERT INTO password_credentials (user_id,password_hash) VALUES (:id,:hash)"),
                {"id": user, "hash": hash_password("correct horse battery staple")},
            )
            for tenant in (tenant_a, tenant_b):
                conn.execute(
                    text(
                        "INSERT INTO tenant_memberships (tenant_id,user_id,role,status) "
                        "VALUES (:tenant,:user,'gate_scanner','active')"
                    ),
                    {"tenant": tenant, "user": user},
                )
        settings = Settings(
            app_env="test", database_url=runtime_url, identity_database_url=identity_url
        )
        yield AuthDatabase(owner, identity, runtime, tenant_a, tenant_b, user, settings)
    finally:
        if runtime:
            runtime.dispose()
        if identity:
            identity.dispose()
        if owner:
            owner.dispose()
        for name in (database, fresh_database):
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
        for role in (identity_role, runtime_role):
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.close()


def _service(db: AuthDatabase) -> AuthService:
    return AuthService(
        db.identity, db.settings, CompromisedPasswordCorpus(None, None), DisabledEmailDelivery()
    )


def test_login_and_revoked_session(auth_db: AuthDatabase) -> None:
    auth = _service(auth_db)
    state, token = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.1"
    )
    assert state == "session"
    assert auth.current("auth-a.example.test", token)[0].id == auth_db.user
    auth.logout(token)
    with pytest.raises(AuthDenied):
        auth.current("auth-a.example.test", token)


def test_cross_tenant_session_switch_denied(auth_db: AuthDatabase) -> None:
    auth = _service(auth_db)
    _, token = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.2"
    )
    with pytest.raises(AuthDenied):
        auth.current("auth-b.example.test", token)


def test_concurrent_sessions_revoke_independently(auth_db: AuthDatabase) -> None:
    auth = _service(auth_db)
    _, first = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.21"
    )
    _, second = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.22"
    )
    auth.logout(first)
    with pytest.raises(AuthDenied):
        auth.current("auth-a.example.test", first)
    assert auth.current("auth-a.example.test", second)[0].id == auth_db.user


def test_inactive_membership_denies_immediately(auth_db: AuthDatabase) -> None:
    auth = _service(auth_db)
    _, token = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.3"
    )
    with auth_db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE tenant_memberships SET status='revoked' "
                "WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": auth_db.tenant_a, "user": auth_db.user},
        )
    with pytest.raises(AuthDenied):
        auth.current("auth-a.example.test", token)
    with auth_db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE tenant_memberships SET status='active' "
                "WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": auth_db.tenant_a, "user": auth_db.user},
        )
    # Reactivating the membership must not resurrect a session issued earlier.
    with pytest.raises(AuthDenied):
        auth.current("auth-a.example.test", token)


def test_status_and_role_transitions_revoke_sessions(auth_db: AuthDatabase) -> None:
    auth = _service(auth_db)
    _, first = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.31"
    )
    _, other_tenant = auth.login(
        "auth-b.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.32"
    )
    with auth_db.owner.begin() as conn:
        conn.execute(
            text("UPDATE users SET status='suspended' WHERE id=:user"),
            {"user": auth_db.user},
        )
        conn.execute(
            text("UPDATE users SET status='active' WHERE id=:user"),
            {"user": auth_db.user},
        )
    for host, token in (("auth-a.example.test", first), ("auth-b.example.test", other_tenant)):
        with pytest.raises(AuthDenied):
            auth.current(host, token)

    _, first = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.33"
    )
    _, other_tenant = auth.login(
        "auth-b.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.34"
    )
    with auth_db.owner.begin() as conn:
        conn.execute(
            text("UPDATE tenant_memberships SET role='tenant_admin' "
                 "WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": auth_db.tenant_a, "user": auth_db.user},
        )
    _, pending_challenge = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.35"
    )
    with auth_db.owner.begin() as conn:
        conn.execute(
            text("UPDATE tenant_memberships SET role='gate_scanner' "
                 "WHERE tenant_id=:tenant AND user_id=:user"),
            {"tenant": auth_db.tenant_a, "user": auth_db.user},
        )
    with pytest.raises(AuthDenied):
        auth.current("auth-a.example.test", first)
    with pytest.raises(AuthDenied, match="challenge expired"):
        auth.verify_mfa("auth-a.example.test", pending_challenge, "000000", ip="127.0.0.35")
    assert auth.current("auth-b.example.test", other_tenant)[0].id == auth_db.user
    with auth_db.owner.connect() as conn:
        assert conn.execute(
            text("SELECT count(*) FROM security_audit_events "
                 "WHERE action='user.status_changed' AND metadata->>'target_user_id'=:user"),
            {"user": str(auth_db.user)},
        ).scalar_one() >= 2
        assert conn.execute(
            text("SELECT count(*) FROM security_audit_events "
                 "WHERE action='membership.changed' AND tenant_id=:tenant "
                 "AND metadata->>'target_user_id'=:user"),
            {"tenant": auth_db.tenant_a, "user": str(auth_db.user)},
        ).scalar_one() >= 2


def test_identity_context_and_runtime_role_restriction(auth_db: AuthDatabase) -> None:
    with auth_db.identity.connect() as conn:
        with conn.begin():
            assert conn.execute(text("SELECT count(*) FROM tenant_memberships")).scalar_one() == 0
            conn.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"),
                {"tenant": str(auth_db.tenant_a)},
            )
            assert conn.execute(text("SELECT count(*) FROM tenant_memberships")).scalar_one() == 1
        with conn.begin():
            assert conn.execute(text("SELECT count(*) FROM tenant_memberships")).scalar_one() == 0
    with auth_db.runtime.connect() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("SELECT count(*) FROM auth_sessions"))
    with pytest.raises(ProgrammingError):
        with auth_db.runtime.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"),
                {"tenant": str(auth_db.tenant_a)},
            )
            conn.execute(
                text("UPDATE tenant_memberships SET role='tenant_admin' "
                     "WHERE tenant_id=:tenant AND user_id=:user"),
                {"tenant": auth_db.tenant_a, "user": auth_db.user},
            )
    with auth_db.identity.connect() as conn, pytest.raises(ProgrammingError):
        conn.execute(text("UPDATE security_audit_events SET action='tampered'"))


def test_authorized_runtime_context_is_transaction_scoped(auth_db: AuthDatabase) -> None:
    with authorized_tenant_session(auth_db.runtime, auth_db.tenant_a) as session:
        assert session.execute(text("SELECT count(*) FROM tenant_memberships")).scalar_one() == 1
    with auth_db.runtime.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM tenant_memberships")).scalar_one() == 0


def test_role_denial_and_failed_login_audit(auth_db: AuthDatabase) -> None:
    auth = _service(auth_db)
    with pytest.raises(AuthDenied):
        auth.login("auth-a.example.test", "staff@example.test", "wrong password", "127.0.0.4")
    with auth_db.owner.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM security_audit_events WHERE action='authentication.failed'")
        ).scalar_one()
        assert count >= 1
    _, token = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.5"
    )
    with pytest.raises(AuthDenied):
        auth.authorize("auth-a.example.test", token, "attendee.export")


def test_session_expiry(auth_db: AuthDatabase) -> None:
    auth = _service(auth_db)
    _, token = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.6"
    )
    with auth_db.owner.begin() as conn:
        conn.execute(
            text("UPDATE auth_sessions SET idle_expires_at=:time WHERE token_digest=:digest"),
            {
                "time": datetime(2000, 1, 1, tzinfo=UTC),
                "digest": __import__("hashlib").sha256(token.encode()).digest(),
            },
        )
    with pytest.raises(AuthDenied):
        auth.current("auth-a.example.test", token)
    _, token = auth.login(
        "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.16"
    )
    with auth_db.owner.begin() as conn:
        conn.execute(
            text("""UPDATE auth_sessions SET created_at=now()-interval '13 hours',
              absolute_expires_at=now()+interval '1 hour',
              idle_expires_at=now()+interval '1 hour'
              WHERE token_digest=:digest"""),
            {"digest": token_digest(token)},
        )
    with pytest.raises(AuthDenied):
        auth.current("auth-a.example.test", token)


class CapturedEmail:
    def __init__(self) -> None:
        self.links: list[str] = []

    def send_link(self, recipient: str, subject: str, link: str) -> None:
        self.links.append(link)


def _corpus(tmp_path: Path) -> CompromisedPasswordCorpus:
    data = (hashlib.sha1(b"known compromised value").hexdigest().upper() + "\n").encode()
    path = tmp_path / "approved-v1.sha1"
    path.write_bytes(data)
    return CompromisedPasswordCorpus(str(path), hashlib.sha256(data).hexdigest())


def _admin_session(db: AuthDatabase) -> str:
    raw = new_token()
    now = datetime.now(UTC)
    with db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE tenant_memberships SET role='tenant_admin' "
                "WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": db.tenant_a, "user": db.user},
        )
        conn.execute(
            text("""INSERT INTO auth_sessions
          (user_id,tenant_id,token_digest,last_seen_at,idle_expires_at,
           absolute_expires_at,mfa_verified_at)
          VALUES (:user,:tenant,:digest,:now,:idle,:absolute,:now)"""),
            {
                "user": db.user,
                "tenant": db.tenant_a,
                "digest": token_digest(raw),
                "now": now,
                "idle": now + timedelta(minutes=15),
                "absolute": now + timedelta(hours=8),
            },
        )
    return raw


def _restore_scanner(db: AuthDatabase) -> None:
    with db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE tenant_memberships SET role='gate_scanner' "
                "WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": db.tenant_a, "user": db.user},
        )


def test_invitation_and_password_reset_replay(
    auth_db: AuthDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = CapturedEmail()
    auth = AuthService(auth_db.identity, auth_db.settings, _corpus(tmp_path), email)
    session = _admin_session(auth_db)
    try:
        event, gate = uuid4(), uuid4()
        now = datetime.now(UTC)
        with auth_db.owner.begin() as conn:
            conn.execute(
                text("""INSERT INTO events
              (id,tenant_id,slug,name,starts_at,ends_at,timezone,status,pii_purge_due_at)
              VALUES (:id,:tenant,'auth-test','Auth Test',:start,:end,
                      'Africa/Lagos','draft',:purge)"""),
                {
                    "id": event,
                    "tenant": auth_db.tenant_a,
                    "start": now,
                    "end": now + timedelta(hours=1),
                    "purge": now + timedelta(days=90),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO gates (id,tenant_id,event_id,name,status) "
                    "VALUES (:id,:tenant,:event,'Main','active')"
                ),
                {"id": gate, "tenant": auth_db.tenant_a, "event": event},
            )
        auth.issue_invitation(
            "auth-a.example.test", session, "invited@example.test", "gate_scanner", event, gate
        )
        invitation = parse_qs(urlsplit(email.links[-1]).fragment)["token"][0]
        with auth_db.identity.connect() as conn:
            with conn.begin():
                conn.execute(
                    text("SELECT set_config('app.tenant_id', :tenant, true)"),
                    {"tenant": str(auth_db.tenant_b)},
                )
                assert (
                    conn.execute(text("SELECT count(*) FROM staff_invitations")).scalar_one() == 0
                )
                with pytest.raises(DBAPIError), conn.begin_nested():
                    conn.execute(
                        text("""INSERT INTO staff_invitations
                          (tenant_id,email,role,token_digest,invited_by,expires_at)
                          VALUES (:tenant,'wrong@example.test','gate_scanner',
                                  :digest,:actor,now())"""),
                        {
                            "tenant": auth_db.tenant_a,
                            "digest": token_digest(new_token()),
                            "actor": auth_db.user,
                        },
                    )
        state, invited_session = auth.accept_invitation(
            "auth-a.example.test", invitation, "safe unlisted invitation password"
        )
        assert state == "session"
        assert (
            auth.current("auth-a.example.test", invited_session)[0].email == "invited@example.test"
        )
        with auth_db.owner.connect() as conn:
            invited_user = conn.execute(
                text("SELECT id FROM users WHERE email='invited@example.test'")
            ).scalar_one()
            assert (
                conn.execute(
                    text("""SELECT count(*) FROM tenant_memberships
                  WHERE tenant_id=:tenant AND user_id=:user AND status='active'"""),
                    {"tenant": auth_db.tenant_a, "user": invited_user},
                ).scalar_one()
                == 1
            )
            assert (
                conn.execute(
                    text("""SELECT count(*) FROM event_assignments
                  WHERE tenant_id=:tenant AND user_id=:user
                    AND event_id=:event AND gate_id=:gate"""),
                    {
                        "tenant": auth_db.tenant_a,
                        "user": invited_user,
                        "event": event,
                        "gate": gate,
                    },
                ).scalar_one()
                == 1
            )
        with pytest.raises(AuthDenied):
            auth.accept_invitation("auth-a.example.test", invitation, "another safe password long")
        with auth_db.owner.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT count(*) FROM event_assignments WHERE user_id=:user"),
                    {"user": invited_user},
                ).scalar_one()
                == 1
            )

        auth.issue_invitation(
            "auth-a.example.test", session, "rollback@example.test", "gate_scanner", event, gate
        )
        rollback_token = parse_qs(urlsplit(email.links[-1]).fragment)["token"][0]

        def fail_assignment(**_: object) -> None:
            raise RuntimeError("simulated assignment failure after membership flush")

        with monkeypatch.context() as patch:
            patch.setattr("app.auth.service.EventAssignment", fail_assignment)
            with pytest.raises(RuntimeError, match="simulated assignment failure"):
                auth.accept_invitation(
                    "auth-a.example.test", rollback_token, "safe rollback test password"
                )
        with auth_db.owner.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT count(*) FROM users WHERE email='rollback@example.test'")
                ).scalar_one()
                == 0
            )
            assert (
                conn.execute(
                    text("SELECT accepted_at FROM staff_invitations WHERE token_digest=:digest"),
                    {"digest": token_digest(rollback_token)},
                ).scalar_one()
                is None
            )
        retry_state, retry_session = auth.accept_invitation(
            "auth-a.example.test", rollback_token, "safe rollback test password"
        )
        assert retry_state == "session"
        assert (
            auth.current("auth-a.example.test", retry_session)[0].email == "rollback@example.test"
        )
        auth.request_reset("auth-a.example.test", "invited@example.test", "127.0.0.7")
        reset = parse_qs(urlsplit(email.links[-1]).fragment)["token"][0]
        auth.request_reset("auth-a.example.test", "invited@example.test", "127.0.0.17")
        second_reset = parse_qs(urlsplit(email.links[-1]).fragment)["token"][0]
        auth.complete_reset("auth-a.example.test", reset, "new safe unlisted password value")
        with pytest.raises(AuthDenied):
            auth.current("auth-a.example.test", invited_session)
        with pytest.raises(AuthDenied):
            auth.complete_reset("auth-a.example.test", reset, "yet another safe password")
        with pytest.raises(AuthDenied):
            auth.complete_reset("auth-a.example.test", second_reset, "yet another safe password")
        auth.request_reset("auth-a.example.test", "invited@example.test", "127.0.0.27")
        suspended_reset = parse_qs(urlsplit(email.links[-1]).fragment)["token"][0]
        with auth_db.owner.begin() as conn:
            conn.execute(
                text("UPDATE users SET status='suspended' WHERE id=:user"),
                {"user": invited_user},
            )
            conn.execute(
                text("UPDATE users SET status='active' WHERE id=:user"),
                {"user": invited_user},
            )
        with pytest.raises(AuthDenied):
            auth.complete_reset("auth-a.example.test", suspended_reset, "yet another safe password")
    finally:
        _restore_scanner(auth_db)


def test_mfa_enrollment_and_replay(auth_db: AuthDatabase) -> None:
    key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    settings = Settings(
        app_env="test",
        database_url=auth_db.settings.database_url,
        identity_database_url=auth_db.settings.identity_database_url,
        auth_encryption_key=key,
    )
    auth = AuthService(
        auth_db.identity, settings, CompromisedPasswordCorpus(None, None), DisabledEmailDelivery()
    )
    with auth_db.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE tenant_memberships SET role='tenant_admin' "
                "WHERE tenant_id=:tenant AND user_id=:user"
            ),
            {"tenant": auth_db.tenant_a, "user": auth_db.user},
        )
    try:
        state, challenge = auth.login(
            "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.8"
        )
        assert state == "enroll"
        second_enrollment_state, stale_enrollment = auth.login(
            "auth-a.example.test",
            "staff@example.test",
            "correct horse battery staple",
            "127.0.0.18",
        )
        assert second_enrollment_state == "enroll"
        secret = auth.enroll_totp("auth-a.example.test", challenge)
        code = totp_code(secret, int(datetime.now(UTC).timestamp() // 30))
        session, recovery = auth.verify_mfa("auth-a.example.test", challenge, code, ip="127.0.0.8")
        assert len(recovery) == 10
        assert auth.current("auth-a.example.test", session)[0].id == auth_db.user
        next_code = totp_code(secret, int(datetime.now(UTC).timestamp() // 30) + 1)
        with pytest.raises(AuthDenied, match="enrollment already completed"):
            auth.verify_mfa(
                "auth-a.example.test", stale_enrollment, next_code, ip="127.0.0.18"
            )
        state, challenge = auth.login(
            "auth-a.example.test", "staff@example.test", "correct horse battery staple", "127.0.0.9"
        )
        assert state == "mfa"
        with pytest.raises(AuthDenied):
            auth.verify_mfa("auth-a.example.test", challenge, code, ip="127.0.0.9")
        second, _ = auth.verify_mfa(
            "auth-a.example.test", challenge, recovery[0], True, "127.0.0.9"
        )
        assert auth.current("auth-a.example.test", second)[0].id == auth_db.user
    finally:
        _restore_scanner(auth_db)
