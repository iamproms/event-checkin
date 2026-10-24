"""Versioned event configuration and tenant-scoped lifecycle audit.

Revision ID: 0007_event_configuration
Revises: 0006_tenant_provisioning
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_event_configuration"
down_revision: str | None = "0006_tenant_provisioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    # Existing v1 seed data may use the older gate spelling. Preserve it.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM events
                 WHERE status NOT IN ('draft','published','closed','cancelled'))
         OR EXISTS (SELECT 1 FROM gates WHERE status NOT IN ('active','inactive')) THEN
        RAISE EXCEPTION 'Review legacy event/gate states before M2-03 migration';
      END IF;
    END $$""")
    op.add_column("events", sa.Column("checkin_opens_at", TS))
    op.add_column("events", sa.Column("checkin_closes_at", TS))
    op.add_column("events", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint(
        "ck_events_status", "events", "status IN ('draft','published','closed','cancelled')"
    )
    op.create_check_constraint("ck_events_revision", "events", "revision > 0")
    op.create_check_constraint(
        "ck_events_registration_pair",
        "events",
        "(registration_opens_at IS NULL) = (registration_closes_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_events_registration_order",
        "events",
        "registration_opens_at IS NULL OR registration_closes_at > registration_opens_at",
    )
    op.create_check_constraint(
        "ck_events_checkin_pair",
        "events",
        "(checkin_opens_at IS NULL) = (checkin_closes_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_events_checkin_order",
        "events",
        "checkin_opens_at IS NULL OR checkin_closes_at > checkin_opens_at",
    )
    op.create_check_constraint(
        "ck_events_purge_due",
        "events",
        "pii_purge_due_at = ends_at + interval '2160 hours'",
    )
    op.create_check_constraint("ck_gates_status", "gates", "status IN ('active','inactive')")
    op.create_table(
        "event_form_versions",
        sa.Column("tenant_id", UUID, primary_key=True),
        sa.Column("event_id", UUID, primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("schema", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id")),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_event_form_versions_event",
        ),
        sa.CheckConstraint("version > 0", name="ck_event_form_versions_positive"),
    )
    op.create_table(
        "event_config_audit",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("occurred_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_event_config_audit_event",
        ),
    )
    op.create_index(
        "ix_event_config_audit_scope",
        "event_config_audit",
        ["tenant_id", "event_id", "occurred_at"],
    )
    # Preserve any populated M1/M2 fixture and its existing form version.
    op.execute("""INSERT INTO event_form_versions (tenant_id,event_id,version,schema)
      SELECT tenant_id,id,form_schema_version,form_schema FROM events""")
    op.create_foreign_key(
        "fk_events_current_form",
        "events",
        "event_form_versions",
        ["tenant_id", "id", "form_schema_version"],
        ["tenant_id", "event_id", "version"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_registrations_form_version",
        "registrations",
        "event_form_versions",
        ["tenant_id", "event_id", "form_schema_version"],
        ["tenant_id", "event_id", "version"],
    )
    for table in ("event_form_versions", "event_config_audit"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)""")
    op.execute("GRANT SELECT, INSERT ON event_form_versions TO eventcheckin_runtime")
    op.execute("GRANT SELECT, INSERT ON event_config_audit TO eventcheckin_runtime")
    op.execute("REVOKE DELETE ON events, gates FROM eventcheckin_runtime")
    op.execute("GRANT SELECT (id, tenant_id, status) ON events TO eventcheckin_identity")
    op.execute("GRANT SELECT (id, tenant_id, event_id, status) ON gates TO eventcheckin_identity")
    op.execute("""CREATE FUNCTION snapshot_initial_event_form() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        INSERT INTO public.event_form_versions(tenant_id,event_id,version,schema)
        VALUES(NEW.tenant_id,NEW.id,NEW.form_schema_version,NEW.form_schema);
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION snapshot_initial_event_form() FROM PUBLIC")
    op.execute("""CREATE TRIGGER events_initial_form AFTER INSERT ON events
      FOR EACH ROW EXECUTE FUNCTION snapshot_initial_event_form()""")
    # Immutable snapshots/audit even if a runtime grant is accidentally widened later.
    op.execute("""CREATE FUNCTION reject_event_history_mutation() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN RAISE EXCEPTION 'Event history is append-only' USING ERRCODE='42501'; END $$""")
    op.execute("REVOKE ALL ON FUNCTION reject_event_history_mutation() FROM PUBLIC")
    for table in ("event_form_versions", "event_config_audit"):
        op.execute(f"""CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
          FOR EACH ROW EXECUTE FUNCTION reject_event_history_mutation()""")
    op.execute("""CREATE FUNCTION guard_event_transition() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF (OLD.status='cancelled' AND NEW.status <> 'cancelled')
           OR (OLD.status='closed' AND NEW.status <> 'closed')
           OR (OLD.status='published' AND NEW.status NOT IN ('published','closed','cancelled'))
           OR (OLD.status='draft' AND NEW.status NOT IN ('draft','published','cancelled')) THEN
          RAISE EXCEPTION 'Invalid event lifecycle transition' USING ERRCODE='23514';
        END IF;
        IF OLD.status='published' AND
          (NEW.starts_at,NEW.ends_at,NEW.timezone,NEW.registration_opens_at,
           NEW.registration_closes_at,NEW.checkin_opens_at,NEW.checkin_closes_at)
          IS DISTINCT FROM
          (OLD.starts_at,OLD.ends_at,OLD.timezone,OLD.registration_opens_at,
           OLD.registration_closes_at,OLD.checkin_opens_at,OLD.checkin_closes_at) THEN
          RAISE EXCEPTION 'Published event schedule is fixed' USING ERRCODE='23514';
        END IF;
        IF OLD.status='published' AND
          (NEW.form_schema_version,NEW.form_schema) IS DISTINCT FROM
          (OLD.form_schema_version,OLD.form_schema) THEN
          RAISE EXCEPTION 'Published event form is fixed' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION guard_event_transition() FROM PUBLIC")
    op.execute("""CREATE TRIGGER events_guard_transition BEFORE UPDATE ON events
      FOR EACH ROW EXECUTE FUNCTION guard_event_transition()""")


def downgrade() -> None:
    # Do not silently destroy populated configuration or registrations.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM event_config_audit)
        OR EXISTS (SELECT 1 FROM registrations)
        OR EXISTS (SELECT 1 FROM events) THEN
        RAISE EXCEPTION 'M2-03 downgrade requires reviewed data migration';
      END IF;
    END $$""")
    op.execute("DROP TRIGGER events_guard_transition ON events")
    op.execute("DROP FUNCTION guard_event_transition()")
    op.execute("DROP TRIGGER events_initial_form ON events")
    op.execute("DROP FUNCTION snapshot_initial_event_form()")
    op.execute("REVOKE SELECT (id, tenant_id, status) ON events FROM eventcheckin_identity")
    op.execute(
        "REVOKE SELECT (id, tenant_id, event_id, status) ON gates FROM eventcheckin_identity"
    )
    op.drop_constraint("fk_events_current_form", "events", type_="foreignkey")
    op.drop_constraint("fk_registrations_form_version", "registrations", type_="foreignkey")
    for table in ("event_config_audit", "event_form_versions"):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.execute("DROP FUNCTION reject_event_history_mutation()")
    op.execute(
        "REVOKE SELECT, INSERT ON event_config_audit, event_form_versions FROM eventcheckin_runtime"
    )
    op.execute("GRANT DELETE ON events, gates TO eventcheckin_runtime")
    op.drop_index("ix_event_config_audit_scope", table_name="event_config_audit")
    op.drop_table("event_config_audit")
    op.drop_table("event_form_versions")
    op.drop_constraint("ck_gates_status", "gates", type_="check")
    for name in (
        "ck_events_status",
        "ck_events_revision",
        "ck_events_registration_pair",
        "ck_events_registration_order",
        "ck_events_checkin_pair",
        "ck_events_checkin_order",
        "ck_events_purge_due",
    ):
        op.drop_constraint(name, "events", type_="check")
    op.drop_column("events", "revision")
    op.drop_column("events", "checkin_closes_at")
    op.drop_column("events", "checkin_opens_at")
