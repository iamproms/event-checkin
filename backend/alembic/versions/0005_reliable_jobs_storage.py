"""Tenant jobs, transactional outbox and private object metadata.

Revision ID: 0005_reliable_jobs_storage
Revises: 0004_auth_session_invalidation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_reliable_jobs_storage"
down_revision: str | None = "0004_auth_session_invalidation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")
NEW_ID = sa.text("gen_random_uuid()")
TENANT_TABLES = ("job_records", "outbox_events", "private_objects")


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_jobs') THEN
        CREATE ROLE eventcheckin_jobs NOLOGIN NOBYPASSRLS;
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_dispatcher') THEN
        CREATE ROLE eventcheckin_dispatcher NOLOGIN NOBYPASSRLS;
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eventcheckin_job_operator') THEN
        CREATE ROLE eventcheckin_job_operator NOLOGIN NOBYPASSRLS;
      END IF;
    END $$""")
    op.create_table(
        "job_records",
        sa.Column("id", UUID, primary_key=True, server_default=NEW_ID),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("event_id", UUID),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("idempotency_key", UUID, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", TS, nullable=False, server_default=NOW),
        sa.Column("notification_after", TS, nullable=False, server_default=NOW),
        sa.Column("lease_token", UUID),
        sa.Column("lease_until", TS),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_job_records_event",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_job_records_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "job_type", "idempotency_key", name="uq_job_records_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','retry_wait','dead')",
            name="ck_job_records_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 20", name="ck_job_attempts"
        ),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_job_progress"),
        sa.CheckConstraint(
            "(status = 'running') = (lease_token IS NOT NULL AND lease_until IS NOT NULL)",
            name="ck_job_running_lease",
        ),
    )
    op.create_index(
        "ix_job_records_due", "job_records", ["status", "next_attempt_at", "created_at"]
    )
    op.create_index(
        "ix_job_records_tenant_status", "job_records", ["tenant_id", "status", "created_at"]
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", UUID, primary_key=True, server_default=NEW_ID),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("published_at", TS),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", TS, nullable=False, server_default=NOW),
        sa.Column("lease_token", UUID),
        sa.Column("lease_until", TS),
        sa.Column("last_error_code", sa.String(64)),
        sa.ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["job_records.tenant_id", "job_records.id"],
            name="fk_outbox_job",
        ),
        sa.UniqueConstraint("job_id", name="uq_outbox_job"),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
        sa.CheckConstraint("(lease_token IS NULL) = (lease_until IS NULL)", name="ck_outbox_lease"),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "outbox_events",
        ["next_attempt_at", "created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_index("ix_outbox_tenant", "outbox_events", ["tenant_id", "created_at"])
    # A job cannot commit without its matching outbox event, even if a caller
    # bypasses the enqueue helper. Deferred evaluation permits either insert order.
    op.execute("""CREATE FUNCTION assert_job_has_outbox()
      RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM public.outbox_events
          WHERE tenant_id = NEW.tenant_id AND job_id = NEW.id
        ) THEN
          RAISE EXCEPTION 'job requires outbox event' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION assert_job_has_outbox() FROM PUBLIC")
    op.execute("""CREATE CONSTRAINT TRIGGER assert_job_has_outbox
      AFTER INSERT ON job_records DEFERRABLE INITIALLY DEFERRED
      FOR EACH ROW EXECUTE FUNCTION assert_job_has_outbox()""")
    op.create_table(
        "private_objects",
        sa.Column("id", UUID, primary_key=True, server_default=NEW_ID),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("event_id", UUID),
        sa.Column("purpose", sa.String(48), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("max_size_bytes", sa.Integer(), nullable=False),
        sa.Column("actual_size_bytes", sa.Integer()),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("completed_at", TS),
        sa.Column("deleted_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_private_objects_event",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_private_objects_tenant_id"),
        sa.UniqueConstraint("object_key", name="uq_private_objects_key"),
        sa.CheckConstraint(
            "status IN ('pending','available','delete_pending','deleted')",
            name="ck_private_objects_status",
        ),
        sa.CheckConstraint(
            "max_size_bytes > 0 AND (actual_size_bytes IS NULL OR "
            "actual_size_bytes BETWEEN 0 AND max_size_bytes)",
            name="ck_private_objects_size",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_private_objects_expiry"),
        sa.CheckConstraint(
            "purpose <> 'internal_test_artifact' OR "
            "(max_size_bytes <= 5242880 AND mime_type IN ('text/plain','application/pdf') "
            "AND expires_at <= created_at + interval '24 hours')",
            name="ck_private_objects_test_policy",
        ),
    )
    op.create_index(
        "ix_private_objects_expiring",
        "private_objects",
        ["expires_at"],
        postgresql_where=sa.text("status <> 'deleted'"),
    )
    op.create_index(
        "ix_private_objects_tenant", "private_objects", ["tenant_id", "event_id", "status"]
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)""")
    op.execute("GRANT SELECT, INSERT ON job_records TO eventcheckin_runtime")
    op.execute("""GRANT UPDATE (status, progress, lease_token, lease_until,
      error_code, finished_at, updated_at) ON job_records TO eventcheckin_runtime""")
    op.execute("GRANT SELECT, INSERT ON outbox_events TO eventcheckin_runtime")
    op.execute("GRANT SELECT, INSERT ON private_objects TO eventcheckin_runtime")
    op.execute("""GRANT UPDATE (object_key, status, actual_size_bytes,
      completed_at, deleted_at) ON private_objects TO eventcheckin_runtime""")
    # Queue worker and outbox dispatcher have distinct metadata-only roles.
    # Neither has business-table, object-table or identity-table grants.
    op.execute("GRANT USAGE ON SCHEMA public TO eventcheckin_jobs")
    op.execute("GRANT USAGE ON SCHEMA public TO eventcheckin_dispatcher")
    op.execute("GRANT USAGE ON SCHEMA public TO eventcheckin_job_operator")
    op.execute("""CREATE POLICY jobs_operator ON job_records
      TO eventcheckin_jobs, eventcheckin_dispatcher USING (true) WITH CHECK (true)""")
    op.execute("GRANT SELECT ON job_records TO eventcheckin_jobs, eventcheckin_dispatcher")
    op.execute("""CREATE POLICY dispatcher_operator ON outbox_events
      TO eventcheckin_dispatcher USING (true) WITH CHECK (true)""")
    op.execute("GRANT SELECT ON outbox_events TO eventcheckin_dispatcher")
    op.execute("""GRANT UPDATE (status, attempts, progress, next_attempt_at,
      lease_token, lease_until, error_code, started_at, finished_at, updated_at)
      ON job_records TO eventcheckin_jobs""")
    op.execute("""GRANT UPDATE (notification_after) ON job_records
      TO eventcheckin_dispatcher""")
    op.execute("""GRANT UPDATE (published_at, attempts, next_attempt_at,
      lease_token, lease_until, last_error_code)
      ON outbox_events TO eventcheckin_dispatcher""")
    op.execute("""CREATE POLICY dead_letter_operator ON job_records
      TO eventcheckin_job_operator USING (true) WITH CHECK (true)""")
    op.execute("GRANT SELECT ON job_records TO eventcheckin_job_operator")
    op.execute("""GRANT UPDATE (status, attempts, next_attempt_at, finished_at,
      error_code, updated_at) ON job_records TO eventcheckin_job_operator""")
    op.execute("GRANT SELECT ON outbox_events TO eventcheckin_job_operator")
    op.execute("""CREATE POLICY outbox_inspection_operator ON outbox_events
      TO eventcheckin_job_operator USING (true)""")
    op.execute("""CREATE POLICY object_cleanup_operator ON private_objects
      TO eventcheckin_job_operator USING (true)""")
    op.execute("GRANT SELECT ON private_objects TO eventcheckin_job_operator")


def downgrade() -> None:
    op.execute("DROP TRIGGER assert_job_has_outbox ON job_records")
    op.execute("DROP FUNCTION assert_job_has_outbox()")
    op.execute("REVOKE SELECT ON private_objects FROM eventcheckin_job_operator")
    op.execute("DROP POLICY object_cleanup_operator ON private_objects")
    op.execute("REVOKE SELECT, UPDATE ON job_records FROM eventcheckin_job_operator")
    op.execute("DROP POLICY dead_letter_operator ON job_records")
    op.execute("REVOKE SELECT ON outbox_events FROM eventcheckin_job_operator")
    op.execute("DROP POLICY outbox_inspection_operator ON outbox_events")
    op.execute("REVOKE SELECT, UPDATE ON outbox_events FROM eventcheckin_dispatcher")
    op.execute("DROP POLICY dispatcher_operator ON outbox_events")
    op.execute("REVOKE SELECT, UPDATE ON job_records FROM eventcheckin_dispatcher")
    op.execute("REVOKE SELECT, UPDATE ON job_records FROM eventcheckin_jobs")
    op.execute("DROP POLICY jobs_operator ON job_records")
    for table in TENANT_TABLES:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM eventcheckin_runtime")
    op.execute("REVOKE USAGE ON SCHEMA public FROM eventcheckin_jobs")
    op.execute("REVOKE USAGE ON SCHEMA public FROM eventcheckin_dispatcher")
    op.execute("REVOKE USAGE ON SCHEMA public FROM eventcheckin_job_operator")
    op.drop_table("private_objects")
    op.drop_table("outbox_events")
    op.drop_table("job_records")
    # Keep the shared NOLOGIN role, which local or deployment login setup may use.
