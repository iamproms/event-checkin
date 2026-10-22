"""Tenant-owned core schema and forced row security.

Revision ID: 0002_tenant_foundation
Revises: 0001_foundation

Requires a migration login with schema CREATE and CREATEROLE. Runtime logins are
provisioned outside migrations and made members of eventcheckin_runtime.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_tenant_foundation"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
CITEXT = postgresql.CITEXT()
JSONB = postgresql.JSONB()
TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")
NEW_ID = sa.text("gen_random_uuid()")
TENANT_TABLES = (
    "tenant_domains",
    "tenant_branding",
    "tenant_memberships",
    "events",
    "gates",
    "registrations",
    "tickets",
    "event_summary",
)


def uuid_id() -> sa.Column[object]:
    return sa.Column("id", UUID, primary_key=True, server_default=NEW_ID)


def tenant_id() -> sa.Column[object]:
    return sa.Column("tenant_id", UUID, nullable=False)


def event_id() -> sa.Column[object]:
    return sa.Column("event_id", UUID, nullable=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_runtime') THEN
        CREATE ROLE eventcheckin_runtime NOLOGIN NOBYPASSRLS;
      END IF;
    END $$""")
    op.create_table(
        "tenants",
        uuid_id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", CITEXT, nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="provisioning"),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.CheckConstraint(
            "status IN ('provisioning','active','suspended','closed')", name="ck_tenants_status"
        ),
    )
    op.create_table(
        "users",
        uuid_id(),
        sa.Column("email", CITEXT, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "tenant_domains",
        uuid_id(),
        tenant_id(),
        sa.Column("hostname", CITEXT, nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("verification_state", sa.String(24), nullable=False),
        sa.Column("tls_state", sa.String(24), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("activated_at", TS),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_tenant_domains_tenant"),
        sa.UniqueConstraint("hostname", name="uq_tenant_domains_hostname"),
    )
    op.create_index("ix_tenant_domains_tenant", "tenant_domains", ["tenant_id"])
    op.create_index(
        "uq_tenant_domains_primary",
        "tenant_domains",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_primary AND verification_state = 'verified' AND tls_state = 'active'"
        ),
    )
    op.create_table(
        "tenant_branding",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("logo_object_key", sa.Text()),
        sa.Column("primary_color", sa.String(7)),
        sa.Column("accent_color", sa.String(7)),
        sa.Column("sender_name", sa.Text()),
        sa.Column("sender_domain", sa.Text()),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_tenant_branding_tenant"),
    )
    op.create_table(
        "tenant_memberships",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("user_id", UUID, primary_key=True),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("invited_at", TS),
        sa.Column("accepted_at", TS),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_tenant_memberships_tenant"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_tenant_memberships_user"),
        sa.CheckConstraint(
            "role IN ('tenant_admin','gate_staff')", name="ck_tenant_memberships_role"
        ),
    )
    op.create_table(
        "events",
        uuid_id(),
        tenant_id(),
        sa.Column("slug", CITEXT, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("ends_at", TS, nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("registration_opens_at", TS),
        sa.Column("registration_closes_at", TS),
        sa.Column("form_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("form_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pii_purge_due_at", TS, nullable=False),
        sa.Column("pii_purged_at", TS),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_events_tenant"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_events_tenant_id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_events_tenant_slug"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_events_time_order"),
        sa.CheckConstraint("form_schema_version > 0", name="ck_events_form_version"),
    )
    op.create_index("ix_events_tenant_status", "events", ["tenant_id", "status"])
    op.create_table(
        "gates",
        uuid_id(),
        tenant_id(),
        event_id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"], ["events.tenant_id", "events.id"], name="fk_gates_event"
        ),
        sa.UniqueConstraint("tenant_id", "event_id", "id", name="uq_gates_event_id"),
        sa.UniqueConstraint("tenant_id", "event_id", "name", name="uq_gates_event_name"),
    )
    op.create_table(
        "registrations",
        uuid_id(),
        tenant_id(),
        event_id(),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", CITEXT, nullable=False),
        sa.Column("phone_e164", sa.String(16), nullable=False),
        sa.Column("custom_answers", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("form_schema_version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("external_ref", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("registered_at", TS, nullable=False, server_default=NOW),
        sa.Column("deleted_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_registrations_event",
        ),
        sa.UniqueConstraint("tenant_id", "event_id", "id", name="uq_registrations_event_id"),
        sa.CheckConstraint(
            "phone_e164 ~ '^\\+[1-9][0-9]{1,14}$'", name="ck_registrations_phone_e164"
        ),
        sa.CheckConstraint(
            "email::text = btrim(email::text) AND length(email::text) > 0",
            name="ck_registrations_email_trimmed",
        ),
        sa.CheckConstraint("source IN ('self','bulk')", name="ck_registrations_source"),
    )
    op.create_index(
        "uq_registrations_email_active",
        "registrations",
        ["tenant_id", "event_id", "email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_registrations_phone_active",
        "registrations",
        ["tenant_id", "event_id", "phone_e164"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_registrations_external_ref",
        "registrations",
        ["tenant_id", "event_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )
    op.create_index(
        "ix_registrations_event_registered",
        "registrations",
        ["tenant_id", "event_id", "registered_at"],
    )
    op.create_table(
        "tickets",
        uuid_id(),
        tenant_id(),
        event_id(),
        sa.Column("registration_id", UUID, nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("token_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("issued_at", TS, nullable=False, server_default=NOW),
        sa.Column("redeemed_at", TS),
        sa.Column("revoked_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "registration_id"],
            ["registrations.tenant_id", "registrations.event_id", "registrations.id"],
            name="fk_tickets_registration",
        ),
        sa.UniqueConstraint("token_digest", name="uq_tickets_token_digest"),
        sa.UniqueConstraint("tenant_id", "event_id", "id", name="uq_tickets_event_id"),
        sa.CheckConstraint("key_version > 0", name="ck_tickets_key_version"),
        sa.CheckConstraint("status IN ('active','used','revoked')", name="ck_tickets_status"),
    )
    op.create_index(
        "uq_tickets_active_registration",
        "tickets",
        ["tenant_id", "event_id", "registration_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_tickets_event", "tickets", ["tenant_id", "event_id"])
    op.create_table(
        "event_summary",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("event_id", UUID, primary_key=True),
        sa.Column("registered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked_in_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_show_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_scan_at", TS),
        sa.Column("finalized_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_event_summary_event",
        ),
        sa.CheckConstraint(
            "registered_count >= 0 AND checked_in_count >= 0 AND no_show_count >= 0 "
            "AND duplicate_count >= 0 AND invalid_count >= 0",
            name="ck_event_summary_counts",
        ),
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)""")
        if table == "tenant_domains":
            op.execute("GRANT SELECT ON tenant_domains TO eventcheckin_runtime")
        else:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO eventcheckin_runtime")
    op.execute("GRANT USAGE ON SCHEMA public TO eventcheckin_runtime")
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_domain_resolver') THEN
        CREATE ROLE eventcheckin_domain_resolver NOLOGIN NOBYPASSRLS;
      END IF;
    END $$""")
    op.execute("GRANT USAGE, CREATE ON SCHEMA public TO eventcheckin_domain_resolver")
    op.execute("GRANT SELECT ON tenant_domains TO eventcheckin_domain_resolver")
    op.execute("""CREATE POLICY domain_lookup ON tenant_domains FOR SELECT
      TO eventcheckin_domain_resolver USING (true)""")
    op.execute("""CREATE FUNCTION resolve_active_tenant_domain(p_hostname citext) RETURNS uuid
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
      SELECT tenant_id FROM public.tenant_domains
      WHERE hostname = p_hostname AND verification_state = 'verified'
        AND tls_state = 'active' AND activated_at IS NOT NULL
      LIMIT 1
    $$""")
    op.execute(
        "ALTER FUNCTION resolve_active_tenant_domain(citext) OWNER TO eventcheckin_domain_resolver"
    )
    op.execute("REVOKE CREATE ON SCHEMA public FROM eventcheckin_domain_resolver")
    op.execute("REVOKE ALL ON FUNCTION resolve_active_tenant_domain(citext) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION resolve_active_tenant_domain(citext) TO eventcheckin_runtime"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION resolve_active_tenant_domain(citext) FROM eventcheckin_runtime"
    )
    op.execute("DROP FUNCTION resolve_active_tenant_domain(citext)")
    op.execute("REVOKE SELECT ON tenant_domains FROM eventcheckin_domain_resolver")
    op.execute("DROP POLICY domain_lookup ON tenant_domains")
    for table in reversed(TENANT_TABLES):
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM eventcheckin_runtime")
    for table in (
        "event_summary",
        "tickets",
        "registrations",
        "gates",
        "events",
        "tenant_memberships",
        "tenant_branding",
        "tenant_domains",
        "users",
        "tenants",
    ):
        op.drop_table(table)
    # The shared runtime group and citext extension may predate this revision.
