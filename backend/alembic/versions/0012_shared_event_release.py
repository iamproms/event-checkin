"""Import-only event mode and shared event-release foundations.

Revision ID: 0012_shared_event_release
Revises: 0011_event_operations
"""

import sqlalchemy as sa

from alembic import op

revision = "0012_shared_event_release"
down_revision = "0011_event_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("registration_mode", sa.String(16), nullable=False, server_default="public"),
    )
    op.add_column("events", sa.Column("description", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_events_registration_mode",
        "events",
        "registration_mode IN ('public','import_only')",
    )
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='eventcheckin_shared_resolver') THEN
        CREATE ROLE eventcheckin_shared_resolver NOLOGIN NOBYPASSRLS;
      END IF;
    END $$""")
    op.execute("GRANT USAGE, CREATE ON SCHEMA public TO eventcheckin_shared_resolver")
    op.execute("GRANT SELECT ON tenant_memberships, tenants TO eventcheckin_shared_resolver")
    op.execute("""CREATE POLICY shared_membership_lookup ON tenant_memberships
      FOR SELECT TO eventcheckin_shared_resolver USING (true)""")
    op.execute("""CREATE FUNCTION shared_login_contexts(p_user uuid)
      RETURNS TABLE(tenant_id uuid, tenant_name text, member_role text)
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
        SELECT m.tenant_id, t.name::text, m.role::text
        FROM public.tenant_memberships m JOIN public.tenants t ON t.id=m.tenant_id
        WHERE m.user_id=p_user AND m.status='active'
          AND t.status='active'
        ORDER BY t.name, m.tenant_id
      $$""")
    op.execute("ALTER FUNCTION shared_login_contexts(uuid) OWNER TO eventcheckin_shared_resolver")
    op.execute("REVOKE ALL ON FUNCTION shared_login_contexts(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION shared_login_contexts(uuid) TO eventcheckin_identity")
    op.execute("REVOKE CREATE ON SCHEMA public FROM eventcheckin_shared_resolver")
    op.create_table(
        "platform_onboarding_requests",
        sa.Column("idempotency_key", sa.UUID(), primary_key=True),
        sa.Column("actor_user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("payload_digest", sa.LargeBinary(), nullable=False),
        sa.Column("organizer_email", sa.Text(), nullable=False),
        sa.Column("organizer_name", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column("requested_event_name", sa.Text(), nullable=True),
        sa.Column("invitation_id", sa.UUID(), nullable=False),
        sa.Column("delivery_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", name="uq_onboarding_request_tenant"),
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON platform_onboarding_requests TO eventcheckin_platform"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE ON platform_onboarding_requests FROM eventcheckin_platform"
    )
    op.drop_table("platform_onboarding_requests")
    op.execute("REVOKE EXECUTE ON FUNCTION shared_login_contexts(uuid) FROM eventcheckin_identity")
    op.execute("DROP FUNCTION shared_login_contexts(uuid)")
    op.execute("DROP POLICY shared_membership_lookup ON tenant_memberships")
    op.execute("REVOKE SELECT ON tenant_memberships, tenants FROM eventcheckin_shared_resolver")
    op.execute("REVOKE USAGE ON SCHEMA public FROM eventcheckin_shared_resolver")
    op.drop_constraint("ck_events_registration_mode", "events", type_="check")
    op.drop_column("events", "description")
    op.drop_column("events", "registration_mode")
