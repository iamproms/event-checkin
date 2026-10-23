"""First-party staff credentials, sessions, MFA and scoped grants.

Revision ID: 0003_staff_identity
Revises: 0002_tenant_foundation

The migration role owns DDL. eventcheckin_identity is NOLOGIN/NOBYPASSRLS;
a separate login receives only its explicitly granted privileges.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_staff_identity"
down_revision: str | None = "0002_tenant_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
CITEXT = postgresql.CITEXT()
JSONB = postgresql.JSONB()
TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")
NEW_ID = sa.text("gen_random_uuid()")
TENANT_TABLES = ("staff_invitations", "event_assignments")
GLOBAL_AUTH_TABLES = (
    "password_credentials",
    "auth_sessions",
    "auth_challenges",
    "password_reset_tokens",
    "totp_credentials",
    "mfa_recovery_codes",
    "auth_rate_limits",
)


def identity_id() -> sa.Column[object]:
    return sa.Column("id", UUID, primary_key=True, server_default=NEW_ID)


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_identity') THEN
        CREATE ROLE eventcheckin_identity NOLOGIN NOBYPASSRLS;
      END IF;
    END $$""")
    op.drop_constraint("ck_tenant_memberships_role", "tenant_memberships", type_="check")
    op.create_check_constraint(
        "ck_tenant_memberships_role",
        "tenant_memberships",
        "role IN ('tenant_owner','tenant_admin','organizer','manager',"
        "'gate_supervisor','gate_scanner','gate_staff')",
    )
    op.create_table(
        "password_credentials",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("changed_at", TS, nullable=False, server_default=NOW),
    )
    op.create_table(
        "auth_sessions",
        identity_id(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("last_seen_at", TS, nullable=False),
        sa.Column("idle_expires_at", TS, nullable=False),
        sa.Column("absolute_expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS),
        sa.Column("mfa_verified_at", TS),
        sa.UniqueConstraint("token_digest", name="uq_auth_sessions_token_digest"),
        sa.CheckConstraint("absolute_expires_at > created_at", name="ck_auth_sessions_absolute"),
        sa.CheckConstraint("idle_expires_at <= absolute_expires_at", name="ck_auth_sessions_idle"),
    )
    op.create_index("ix_auth_sessions_user", "auth_sessions", ["user_id", "revoked_at"])
    op.create_table(
        "auth_challenges",
        identity_id(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("consumed_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("token_digest", name="uq_auth_challenges_token_digest"),
        sa.CheckConstraint("purpose IN ('mfa','enroll')", name="ck_auth_challenges_purpose"),
    )
    op.create_table(
        "staff_invitations",
        identity_id(),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", CITEXT, nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("event_id", UUID),
        sa.Column("gate_id", UUID),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("invited_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("accepted_at", TS),
        sa.Column("revoked_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_invitations_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "invited_by"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_invitations_inviter_member",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "gate_id"],
            ["gates.tenant_id", "gates.event_id", "gates.id"],
            name="fk_invitations_gate",
        ),
        sa.UniqueConstraint("token_digest", name="uq_staff_invitations_token_digest"),
        sa.CheckConstraint(
            "gate_id IS NULL OR event_id IS NOT NULL", name="ck_invitations_gate_event"
        ),
    )
    op.create_index(
        "ix_staff_invitations_tenant_email", "staff_invitations", ["tenant_id", "email"]
    )
    op.create_table(
        "password_reset_tokens",
        identity_id(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("consumed_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("token_digest", name="uq_password_reset_tokens_digest"),
    )
    op.create_table(
        "totp_credentials",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("encrypted_secret", sa.LargeBinary(), nullable=False),
        sa.Column("key_id", sa.String(32), nullable=False),
        sa.Column("confirmed_at", TS),
        sa.Column("last_accepted_step", sa.BigInteger()),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
    )
    op.create_table(
        "mfa_recovery_codes",
        identity_id(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_digest", sa.LargeBinary(), nullable=False),
        sa.Column("used_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("code_digest", name="uq_mfa_recovery_codes_digest"),
    )
    op.create_table(
        "event_assignments",
        identity_id(),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("gate_id", UUID),
        sa.Column("valid_from", TS, nullable=False),
        sa.Column("valid_until", TS),
        sa.Column("revoked_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_assignments_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_assignments_member",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "gate_id"],
            ["gates.tenant_id", "gates.event_id", "gates.id"],
            name="fk_assignments_gate",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="ck_assignments_time"
        ),
    )
    op.create_index(
        "ix_event_assignments_scope",
        "event_assignments",
        ["tenant_id", "user_id", "event_id", "gate_id"],
    )
    op.create_table(
        "platform_grants",
        identity_id(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id")),
        sa.Column("valid_from", TS, nullable=False),
        sa.Column("valid_until", TS, nullable=False),
        sa.Column("revoked_at", TS),
        sa.Column("granted_by", UUID, sa.ForeignKey("users.id")),
        sa.CheckConstraint("valid_until > valid_from", name="ck_platform_grants_time"),
    )
    op.create_index("ix_platform_grants_user", "platform_grants", ["user_id", "operation"])
    op.create_table(
        "security_audit_events",
        identity_id(),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id")),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("occurred_at", TS, nullable=False, server_default=NOW),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_table(
        "auth_rate_limits",
        sa.Column("key_digest", sa.LargeBinary(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("window_started_at", TS, nullable=False),
        sa.Column("blocked_until", TS),
        sa.CheckConstraint("attempts >= 0", name="ck_auth_rate_limits_attempts"),
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)""")
    op.execute("GRANT USAGE ON SCHEMA public TO eventcheckin_identity")
    op.execute(
        "GRANT EXECUTE ON FUNCTION resolve_active_tenant_domain(citext) TO eventcheckin_identity"
    )
    op.execute("GRANT SELECT ON tenants TO eventcheckin_identity")
    op.execute("GRANT SELECT, INSERT, UPDATE ON users TO eventcheckin_identity")
    op.execute("GRANT SELECT, INSERT, UPDATE ON tenant_memberships TO eventcheckin_identity")
    for table in TENANT_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO eventcheckin_identity")
    op.execute("GRANT SELECT ON platform_grants TO eventcheckin_identity")
    for table in GLOBAL_AUTH_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO eventcheckin_identity")
    op.execute("GRANT SELECT, INSERT ON security_audit_events TO eventcheckin_identity")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON security_audit_events FROM eventcheckin_identity")
    for table in GLOBAL_AUTH_TABLES:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE ON {table} FROM eventcheckin_identity")
    op.execute("REVOKE SELECT ON platform_grants FROM eventcheckin_identity")
    for table in TENANT_TABLES:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM eventcheckin_identity")
    op.execute("REVOKE SELECT, INSERT, UPDATE ON tenant_memberships FROM eventcheckin_identity")
    op.execute("REVOKE SELECT, INSERT, UPDATE ON users FROM eventcheckin_identity")
    op.execute("REVOKE SELECT ON tenants FROM eventcheckin_identity")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION resolve_active_tenant_domain(citext) FROM eventcheckin_identity"
    )
    for table in (
        "auth_rate_limits",
        "security_audit_events",
        "platform_grants",
        "event_assignments",
        "mfa_recovery_codes",
        "totp_credentials",
        "password_reset_tokens",
        "staff_invitations",
        "auth_challenges",
        "auth_sessions",
        "password_credentials",
    ):
        op.drop_table(table)
    op.drop_constraint("ck_tenant_memberships_role", "tenant_memberships", type_="check")
    op.create_check_constraint(
        "ck_tenant_memberships_role",
        "tenant_memberships",
        "role IN ('tenant_admin','gate_staff')",
    )
    # The shared NOLOGIN identity group may predate this revision.
