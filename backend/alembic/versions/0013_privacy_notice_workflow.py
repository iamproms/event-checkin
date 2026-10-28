"""Platform-approved notice drafts and auditable import authorization.

Revision ID: 0013_privacy_notice_workflow
Revises: 0012_shared_event_release
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_privacy_notice_workflow"
down_revision = "0012_shared_event_release"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("registration_notice_versions", "approved_at", nullable=True)
    op.add_column("registration_notice_versions", sa.Column("created_by", sa.UUID(), nullable=True))
    op.add_column(
        "registration_notice_versions", sa.Column("approved_by", sa.UUID(), nullable=True)
    )
    op.add_column(
        "registration_notice_versions", sa.Column("approval_reference", sa.Text(), nullable=True)
    )
    op.add_column(
        "registration_notice_versions",
        sa.Column("test_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "registration_notice_versions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_foreign_key(
        "fk_notice_created_by", "registration_notice_versions", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_notice_approved_by", "registration_notice_versions", "users", ["approved_by"], ["id"]
    )
    op.create_check_constraint(
        "ck_notice_active_approved",
        "registration_notice_versions",
        "NOT active OR approved_at IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_notice_approval_reference",
        "registration_notice_versions",
        "approval_reference IS NULL OR length(btrim(approval_reference)) BETWEEN 1 AND 500",
    )
    op.execute("""CREATE OR REPLACE FUNCTION guard_registration_notice_version() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF (NEW.body,NEW.lawful_basis,NEW.sha256,NEW.test_only,NEW.created_by,NEW.created_at)
           IS DISTINCT FROM (OLD.body,OLD.lawful_basis,OLD.sha256,
                             OLD.test_only,OLD.created_by,OLD.created_at)
           OR (OLD.approved_at IS NOT NULL AND
               (NEW.approved_at,NEW.approved_by,NEW.approval_reference)
               IS DISTINCT FROM (OLD.approved_at,OLD.approved_by,OLD.approval_reference))
           OR (OLD.approved_at IS NULL AND NEW.approved_at IS NOT NULL AND
               (NEW.approved_by IS NULL OR NEW.approval_reference IS NULL))
           OR (OLD.approved_at IS NULL AND NEW.approved_at IS NULL AND
               (NEW.approved_by,NEW.approval_reference)
               IS DISTINCT FROM (OLD.approved_by,OLD.approval_reference)) THEN
          RAISE EXCEPTION 'Approved notice content is immutable' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE (approved_at, approved_by, approval_reference, active) "
        "ON registration_notice_versions TO eventcheckin_platform"
    )
    op.execute(
        "GRANT INSERT, SELECT (id, occurred_at) ON security_audit_events TO eventcheckin_runtime"
    )
    op.execute("""CREATE POLICY platform_notice_control ON registration_notice_versions
      TO eventcheckin_platform
      USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)""")
    op.add_column(
        "participant_imports",
        sa.Column("authorization_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "participant_imports", sa.Column("authorization_confirmed_by", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_import_authorization_actor",
        "participant_imports",
        "users",
        ["authorization_confirmed_by"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_import_authorization_evidence",
        "participant_imports",
        "(authorization_confirmed_at IS NULL) = (authorization_confirmed_by IS NULL)",
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM registration_notice_versions
                 WHERE created_by IS NOT NULL OR approved_at IS NULL)
         OR EXISTS (SELECT 1 FROM participant_imports
                    WHERE authorization_confirmed_at IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot downgrade privacy notice workflow while new evidence exists';
      END IF;
    END $$""")
    op.drop_constraint("ck_import_authorization_evidence", "participant_imports", type_="check")
    op.drop_constraint("fk_import_authorization_actor", "participant_imports", type_="foreignkey")
    op.drop_column("participant_imports", "authorization_confirmed_by")
    op.drop_column("participant_imports", "authorization_confirmed_at")
    op.execute("DROP POLICY platform_notice_control ON registration_notice_versions")
    op.execute(
        "REVOKE INSERT, SELECT (id, occurred_at) ON security_audit_events FROM eventcheckin_runtime"
    )
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE (approved_at, approved_by, approval_reference, active) "
        "ON registration_notice_versions FROM eventcheckin_platform"
    )
    op.execute("""CREATE OR REPLACE FUNCTION guard_registration_notice_version() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF (NEW.body,NEW.lawful_basis,NEW.sha256,NEW.approved_at)
           IS DISTINCT FROM (OLD.body,OLD.lawful_basis,OLD.sha256,OLD.approved_at) THEN
          RAISE EXCEPTION 'Approved notice content is immutable' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.drop_constraint(
        "ck_notice_approval_reference", "registration_notice_versions", type_="check"
    )
    op.drop_constraint("ck_notice_active_approved", "registration_notice_versions", type_="check")
    op.drop_constraint("fk_notice_approved_by", "registration_notice_versions", type_="foreignkey")
    op.drop_constraint("fk_notice_created_by", "registration_notice_versions", type_="foreignkey")
    for name in ("created_at", "test_only", "approval_reference", "approved_by", "created_by"):
        op.drop_column("registration_notice_versions", name)
    op.alter_column("registration_notice_versions", "approved_at", nullable=False)
