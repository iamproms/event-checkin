"""Audited ticket commands and idempotent delivery intents.

Revision ID: 0010_ticket_delivery
Revises: 0009_public_registration
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_ticket_delivery"
down_revision: str | None = "0009_public_registration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "ticket_delivery_intents",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("ticket_id", UUID, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_message_id", sa.Text()),
        sa.Column("error_code", sa.String(48)),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("sent_at", TS),
        sa.Column("delivered_at", TS),
        sa.Column("failed_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "ticket_id"],
            ["tickets.tenant_id", "tickets.event_id", "tickets.id"],
            name="fk_ticket_delivery_ticket",
        ),
        sa.UniqueConstraint("tenant_id", "event_id", "id", name="uq_ticket_delivery_scope"),
        sa.UniqueConstraint("provider_message_id", name="uq_ticket_delivery_provider_id"),
        sa.CheckConstraint("kind IN ('issue','resend','reissue')", name="ck_ticket_delivery_kind"),
        sa.CheckConstraint(
            "status IN ('queued','sending','sent','delivered','failed','bounced')",
            name="ck_ticket_delivery_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_ticket_delivery_attempts"),
    )
    op.create_index(
        "ix_ticket_delivery_ticket",
        "ticket_delivery_intents",
        ["tenant_id", "event_id", "ticket_id", "created_at"],
    )
    op.create_table(
        "ticket_audit",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("ticket_id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("occurred_at", TS, nullable=False, server_default=NOW),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "ticket_id"],
            ["tickets.tenant_id", "tickets.event_id", "tickets.id"],
            name="fk_ticket_audit_ticket",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_ticket_audit_actor_member",
        ),
    )
    op.create_index(
        "ix_ticket_audit_scope",
        "ticket_audit",
        ["tenant_id", "event_id", "ticket_id", "occurred_at"],
    )
    for table in ("ticket_delivery_intents", "ticket_audit"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)""")
    op.execute("GRANT SELECT, INSERT ON ticket_delivery_intents TO eventcheckin_runtime")
    op.execute("""GRANT UPDATE
      (status, attempts, provider_message_id, error_code, sent_at, delivered_at, failed_at)
      ON ticket_delivery_intents TO eventcheckin_runtime""")
    op.execute("GRANT SELECT, INSERT ON ticket_audit TO eventcheckin_runtime")
    # The existing active-ticket partial unique index is the concurrency backstop.
    # No ciphertext or token digest is granted to platform or identity roles.
    op.execute("""CREATE FUNCTION guard_ticket_transition() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF OLD.status IN ('used','revoked') AND NEW.status <> OLD.status THEN
          RAISE EXCEPTION 'Terminal ticket cannot reactivate' USING ERRCODE='23514';
        END IF;
        IF (NEW.token_digest,NEW.token_ciphertext,NEW.key_version,NEW.registration_id,
            NEW.tenant_id,NEW.event_id) IS DISTINCT FROM
           (OLD.token_digest,OLD.token_ciphertext,OLD.key_version,OLD.registration_id,
            OLD.tenant_id,OLD.event_id) THEN
          RAISE EXCEPTION 'Ticket credential is immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION guard_ticket_transition() FROM PUBLIC")
    op.execute("""CREATE TRIGGER tickets_guard_transition BEFORE UPDATE ON tickets
      FOR EACH ROW EXECUTE FUNCTION guard_ticket_transition()""")
    op.execute("""CREATE FUNCTION reject_ticket_audit_mutation() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN RAISE EXCEPTION 'Ticket audit is append-only' USING ERRCODE='42501'; END $$""")
    op.execute("REVOKE ALL ON FUNCTION reject_ticket_audit_mutation() FROM PUBLIC")
    op.execute("""CREATE TRIGGER ticket_audit_immutable BEFORE UPDATE OR DELETE ON ticket_audit
      FOR EACH ROW EXECUTE FUNCTION reject_ticket_audit_mutation()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM ticket_delivery_intents)
         OR EXISTS (SELECT 1 FROM ticket_audit)
         OR EXISTS (SELECT 1 FROM tickets) THEN
        RAISE EXCEPTION 'Ticket downgrade requires reviewed data migration';
      END IF;
    END $$""")
    op.execute("DROP TRIGGER ticket_audit_immutable ON ticket_audit")
    op.execute("DROP FUNCTION reject_ticket_audit_mutation()")
    op.execute("DROP TRIGGER tickets_guard_transition ON tickets")
    op.execute("DROP FUNCTION guard_ticket_transition()")
    op.execute("REVOKE SELECT, INSERT ON ticket_audit FROM eventcheckin_runtime")
    op.execute("""REVOKE UPDATE
      (status, attempts, provider_message_id, error_code, sent_at, delivered_at, failed_at)
      ON ticket_delivery_intents FROM eventcheckin_runtime""")
    op.execute("REVOKE SELECT, INSERT ON ticket_delivery_intents FROM eventcheckin_runtime")
    op.drop_index("ix_ticket_audit_scope", table_name="ticket_audit")
    op.drop_table("ticket_audit")
    op.drop_index("ix_ticket_delivery_ticket", table_name="ticket_delivery_intents")
    op.drop_table("ticket_delivery_intents")
