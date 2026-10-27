"""Bulk registration imports and server-confirmed gate redemption.

Revision ID: 0011_event_operations
Revises: 0010_ticket_delivery
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_event_operations"
down_revision: str | None = "0010_ticket_delivery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")
NEW_ID = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.alter_column("registrations", "phone_e164", nullable=True)
    op.create_check_constraint(
        "ck_registrations_self_phone_required",
        "registrations",
        "source <> 'self' OR phone_e164 IS NOT NULL",
    )
    op.alter_column("registration_consents", "acknowledged_at", nullable=True)
    op.drop_constraint("ck_registration_consents_source", "registration_consents", type_="check")
    op.create_check_constraint(
        "ck_registration_consents_source",
        "registration_consents",
        "source IN ('self','bulk')",
    )
    op.create_check_constraint(
        "ck_registration_consents_acknowledgement",
        "registration_consents",
        "(source='self' AND acknowledged_at IS NOT NULL) OR "
        "(source='bulk' AND acknowledged_at IS NULL)",
    )
    op.create_table(
        "participant_imports",
        sa.Column("id", UUID, primary_key=True, server_default=NEW_ID),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("created_by", UUID, nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="uploaded"),
        sa.Column("mapping", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notice_version", sa.Integer()),
        sa.Column("lawful_basis", sa.Text()),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_job_id", UUID),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("validated_at", TS),
        sa.Column("committed_at", TS),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_participant_imports_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_participant_imports_actor",
        ),
        sa.UniqueConstraint("tenant_id", "event_id", "id", name="uq_participant_import_scope"),
        sa.UniqueConstraint(
            "tenant_id", "event_id", "file_sha256", name="uq_participant_import_file"
        ),
        sa.CheckConstraint(
            "status IN ('uploaded','validated','queued','processing','completed','failed')",
            name="ck_participant_import_status",
        ),
        sa.CheckConstraint(
            "row_count >= 0 AND valid_count >= 0 AND invalid_count >= 0 "
            "AND duplicate_count >= 0 AND imported_count >= 0",
            name="ck_participant_import_counts",
        ),
    )
    op.create_index(
        "ix_participant_imports_event",
        "participant_imports",
        ["tenant_id", "event_id", "created_at"],
    )
    op.create_table(
        "participant_import_rows",
        sa.Column("id", UUID, primary_key=True, server_default=NEW_ID),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("import_id", UUID, nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", JSONB, nullable=False),
        sa.Column("normalized_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("error_codes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("registration_id", UUID),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "import_id"],
            [
                "participant_imports.tenant_id",
                "participant_imports.event_id",
                "participant_imports.id",
            ],
            name="fk_participant_import_rows_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "registration_id"],
            ["registrations.tenant_id", "registrations.event_id", "registrations.id"],
            name="fk_participant_import_rows_registration",
        ),
        sa.UniqueConstraint("tenant_id", "import_id", "row_number", name="uq_import_row_number"),
        sa.CheckConstraint("row_number > 1", name="ck_import_row_number"),
        sa.CheckConstraint(
            "status IN ('pending','valid','invalid','duplicate','imported')",
            name="ck_participant_import_row_status",
        ),
    )
    op.create_index(
        "ix_participant_import_rows_batch",
        "participant_import_rows",
        ["tenant_id", "event_id", "import_id", "row_number"],
    )
    op.create_table(
        "checkin_attempts",
        sa.Column("id", UUID, primary_key=True, server_default=NEW_ID),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("gate_id", UUID, nullable=False),
        sa.Column("ticket_id", UUID),
        sa.Column("registration_id", UUID),
        sa.Column("scanner_user_id", UUID, nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("occurred_at", TS, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "gate_id"],
            ["gates.tenant_id", "gates.event_id", "gates.id"],
            name="fk_checkin_attempts_gate",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "ticket_id"],
            ["tickets.tenant_id", "tickets.event_id", "tickets.id"],
            name="fk_checkin_attempts_ticket",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id", "registration_id"],
            ["registrations.tenant_id", "registrations.event_id", "registrations.id"],
            name="fk_checkin_attempts_registration",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "scanner_user_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_checkin_attempts_scanner",
        ),
        sa.CheckConstraint(
            "outcome IN ('accepted','duplicate','revoked','invalid')",
            name="ck_checkin_attempts_outcome",
        ),
        sa.CheckConstraint(
            "(outcome = 'invalid' AND ticket_id IS NULL AND registration_id IS NULL) OR "
            "(outcome <> 'invalid' AND ticket_id IS NOT NULL AND registration_id IS NOT NULL)",
            name="ck_checkin_attempts_ticket_evidence",
        ),
    )
    op.create_index(
        "ix_checkin_attempts_event",
        "checkin_attempts",
        ["tenant_id", "event_id", "occurred_at"],
    )
    op.create_index(
        "ix_checkin_attempts_gate",
        "checkin_attempts",
        ["tenant_id", "event_id", "gate_id", "occurred_at"],
    )
    op.create_index(
        "uq_checkin_accepted_ticket",
        "checkin_attempts",
        ["tenant_id", "event_id", "ticket_id"],
        unique=True,
        postgresql_where=sa.text("outcome = 'accepted'"),
    )

    for table in ("participant_imports", "participant_import_rows", "checkin_attempts"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_isolation ON {table}
          USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
          WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)""")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO eventcheckin_runtime")
    op.execute("""CREATE FUNCTION purge_participant_import_pii() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN
        IF OLD.pii_purged_at IS NULL AND NEW.pii_purged_at IS NOT NULL THEN
          DELETE FROM participant_import_rows
            WHERE tenant_id=NEW.tenant_id AND event_id=NEW.id;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER participant_import_pii_purge
      AFTER UPDATE OF pii_purged_at ON events
      FOR EACH ROW EXECUTE FUNCTION purge_participant_import_pii()""")


def downgrade() -> None:
    # A populated event database must not silently lose bulk consent evidence.
    has_bulk_evidence = op.get_bind().scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM registration_consents WHERE source='bulk')")
    )
    if has_bulk_evidence:
        raise RuntimeError("Cannot downgrade while bulk consent evidence exists")
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM registrations WHERE phone_e164 IS NULL)")
    ):
        raise RuntimeError("Cannot downgrade while registrations without a phone exist")
    op.execute("DROP TRIGGER participant_import_pii_purge ON events")
    op.execute("DROP FUNCTION purge_participant_import_pii()")
    for table in ("checkin_attempts", "participant_import_rows", "participant_imports"):
        op.execute(f"DROP POLICY tenant_isolation ON {table}")
    op.drop_index("uq_checkin_accepted_ticket", table_name="checkin_attempts")
    op.drop_index("ix_checkin_attempts_gate", table_name="checkin_attempts")
    op.drop_index("ix_checkin_attempts_event", table_name="checkin_attempts")
    op.drop_table("checkin_attempts")
    op.drop_index("ix_participant_import_rows_batch", table_name="participant_import_rows")
    op.drop_table("participant_import_rows")
    op.drop_index("ix_participant_imports_event", table_name="participant_imports")
    op.drop_table("participant_imports")
    op.drop_constraint(
        "ck_registration_consents_acknowledgement", "registration_consents", type_="check"
    )
    op.drop_constraint("ck_registration_consents_source", "registration_consents", type_="check")
    op.create_check_constraint(
        "ck_registration_consents_source", "registration_consents", "source = 'self'"
    )
    op.alter_column("registration_consents", "acknowledged_at", nullable=False)
    op.drop_constraint("ck_registrations_self_phone_required", "registrations", type_="check")
    op.alter_column("registrations", "phone_e164", nullable=False)
