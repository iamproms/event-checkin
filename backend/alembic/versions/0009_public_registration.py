"""Versioned notice evidence for public, tenant-scoped registration.

Revision ID: 0009_public_registration
Revises: 0008_tenant_branding
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_public_registration"
down_revision: str | None = "0008_tenant_branding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "registration_notice_versions",
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("lawful_basis", sa.Text(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(), nullable=False),
        sa.Column("approved_at", TS, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("version > 0", name="ck_registration_notice_version"),
        sa.CheckConstraint("octet_length(sha256) = 32", name="ck_registration_notice_digest"),
        sa.CheckConstraint(
            "length(btrim(body)) BETWEEN 1 AND 20000", name="ck_registration_notice_body"
        ),
        sa.CheckConstraint(
            "length(btrim(lawful_basis)) BETWEEN 1 AND 500",
            name="ck_registration_notice_basis",
        ),
    )
    op.create_index(
        "uq_registration_notice_active",
        "registration_notice_versions",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "registration_consents",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("registration_id", UUID, nullable=False),
        sa.Column("notice_version", sa.Integer(), nullable=False),
        sa.Column("notice_digest", sa.LargeBinary(), nullable=False),
        sa.Column("lawful_basis", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "marketing_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("source", sa.String(16), nullable=False, server_default="self"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "registration_id"],
            ["registrations.tenant_id", "registrations.event_id", "registrations.id"],
            name="fk_registration_consents_registration",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "notice_version"],
            ["registration_notice_versions.tenant_id", "registration_notice_versions.version"],
            name="fk_registration_consents_notice",
        ),
        sa.UniqueConstraint(
            "tenant_id", "event_id", "registration_id", name="uq_registration_consents_registration"
        ),
        sa.CheckConstraint(
            "octet_length(notice_digest) = 32", name="ck_registration_consents_digest"
        ),
        sa.CheckConstraint("source = 'self'", name="ck_registration_consents_source"),
    )
    for table in ("registration_notice_versions", "registration_consents"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)""")
    op.execute("GRANT SELECT ON registration_notice_versions TO eventcheckin_runtime")
    op.execute("GRANT SELECT, INSERT ON registration_consents TO eventcheckin_runtime")
    op.execute("""CREATE FUNCTION guard_registration_notice_version() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF (NEW.body,NEW.lawful_basis,NEW.sha256,NEW.approved_at)
           IS DISTINCT FROM (OLD.body,OLD.lawful_basis,OLD.sha256,OLD.approved_at) THEN
          RAISE EXCEPTION 'Approved notice content is immutable' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION guard_registration_notice_version() FROM PUBLIC")
    op.execute("""CREATE TRIGGER registration_notice_immutable
      BEFORE UPDATE ON registration_notice_versions
      FOR EACH ROW EXECUTE FUNCTION guard_registration_notice_version()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM registration_consents)
         OR EXISTS (SELECT 1 FROM registration_notice_versions) THEN
        RAISE EXCEPTION 'Registration downgrade requires reviewed data migration';
      END IF;
    END $$""")
    op.execute("DROP TRIGGER registration_notice_immutable ON registration_notice_versions")
    op.execute("DROP FUNCTION guard_registration_notice_version()")
    op.execute("REVOKE SELECT, INSERT ON registration_consents FROM eventcheckin_runtime")
    op.execute("REVOKE SELECT ON registration_notice_versions FROM eventcheckin_runtime")
    op.drop_table("registration_consents")
    op.drop_index("uq_registration_notice_active", table_name="registration_notice_versions")
    op.drop_table("registration_notice_versions")
