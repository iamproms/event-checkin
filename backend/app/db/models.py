"""M1-02 relational contract. Feature-specific tables follow their owning milestones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="provisioning")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('provisioning','active','suspended','closed')", name="ck_tenants_status"
        ),
        UniqueConstraint("slug", name="uq_tenants_slug"),
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)


class TenantDomain(Base):
    __tablename__ = "tenant_domains"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", name="fk_tenant_domains_tenant"),
        nullable=False,
    )
    hostname: Mapped[str] = mapped_column(CITEXT, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    verification_state: Mapped[str] = mapped_column(String(24), nullable=False)
    tls_state: Mapped[str] = mapped_column(String(24), nullable=False)
    routing_state: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="reserved"
    )
    claim_digest: Mapped[bytes | None] = mapped_column(LargeBinary)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ownership_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ownership_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tls_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tls_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edge_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    smoke_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    next_reconcile_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_tenant_domains_hostname"),
        UniqueConstraint("tenant_id", "id", name="uq_tenant_domains_tenant_id"),
        Index("ix_tenant_domains_tenant", "tenant_id"),
        Index(
            "uq_tenant_domains_primary",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_primary AND routing_state = 'active'"),
        ),
        Index(
            "uq_tenant_domains_fallback",
            "tenant_id",
            unique=True,
            postgresql_where=text("kind = 'fallback'"),
        ),
        CheckConstraint("kind IN ('custom','fallback')", name="ck_domain_kind"),
        CheckConstraint(
            "verification_state IN ('pending','checking','verified','failed')",
            name="ck_domain_verification",
        ),
        CheckConstraint(
            "tls_state IN ('pending','issuing','active','failed')", name="ck_domain_tls"
        ),
        CheckConstraint(
            "routing_state IN ('reserved','ready','active','deactivated')", name="ck_domain_routing"
        ),
        CheckConstraint(
            "routing_state <> 'active' OR (verification_state='verified' "
            "AND tls_state='active' AND edge_ready AND activated_at IS NOT NULL "
            "AND ownership_valid_until IS NOT NULL AND tls_valid_until IS NOT NULL "
            "AND smoke_checked_at IS NOT NULL)",
            name="ck_domain_active_gates",
        ),
    )


class TenantBranding(Base):
    __tablename__ = "tenant_branding"
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", name="fk_tenant_branding_tenant"),
        primary_key=True,
    )
    logo_object_key: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str | None] = mapped_column(String(7))
    accent_color: Mapped[str | None] = mapped_column(String(7))
    sender_name: Mapped[str | None] = mapped_column(Text)
    sender_domain: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", name="fk_tenant_memberships_tenant"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", name="fk_tenant_memberships_user"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "role IN ('tenant_owner','tenant_admin','organizer','manager',"
            "'gate_supervisor','gate_scanner','gate_staff')",
            name="ck_tenant_memberships_role",
        ),
    )


class Event(Base):
    __tablename__ = "events"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", name="fk_events_tenant"), nullable=False
    )
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    registration_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkin_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkin_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    form_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    form_schema: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    pii_purge_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pii_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "id", "form_schema_version"],
            [
                "event_form_versions.tenant_id",
                "event_form_versions.event_id",
                "event_form_versions.version",
            ],
            name="fk_events_current_form",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_events_tenant_id"),
        UniqueConstraint("tenant_id", "slug", name="uq_events_tenant_slug"),
        CheckConstraint("ends_at > starts_at", name="ck_events_time_order"),
        CheckConstraint("form_schema_version > 0", name="ck_events_form_version"),
        CheckConstraint(
            "status IN ('draft','published','closed','cancelled')", name="ck_events_status"
        ),
        CheckConstraint("revision > 0", name="ck_events_revision"),
        CheckConstraint(
            "(registration_opens_at IS NULL) = (registration_closes_at IS NULL)",
            name="ck_events_registration_pair",
        ),
        CheckConstraint(
            "registration_opens_at IS NULL OR registration_closes_at > registration_opens_at",
            name="ck_events_registration_order",
        ),
        CheckConstraint(
            "(checkin_opens_at IS NULL) = (checkin_closes_at IS NULL)",
            name="ck_events_checkin_pair",
        ),
        CheckConstraint(
            "checkin_opens_at IS NULL OR checkin_closes_at > checkin_opens_at",
            name="ck_events_checkin_order",
        ),
        CheckConstraint(
            "pii_purge_due_at = ends_at + interval '2160 hours'", name="ck_events_purge_due"
        ),
        Index("ix_events_tenant_status", "tenant_id", "status"),
    )


class Gate(Base):
    __tablename__ = "gates"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"], ["events.tenant_id", "events.id"], name="fk_gates_event"
        ),
        UniqueConstraint("tenant_id", "event_id", "id", name="uq_gates_event_id"),
        UniqueConstraint("tenant_id", "event_id", "name", name="uq_gates_event_name"),
        CheckConstraint("status IN ('active','inactive')", name="ck_gates_status"),
    )


class EventFormVersion(Base):
    __tablename__ = "event_form_versions"
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_event_form_versions_event",
        ),
        CheckConstraint("version > 0", name="ck_event_form_versions_positive"),
    )


class EventConfigAudit(Base):
    __tablename__ = "event_config_audit"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_event_config_audit_event",
        ),
    )


class Registration(Base):
    __tablename__ = "registrations"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(16), nullable=False)
    custom_answers: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    form_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_registrations_event",
        ),
        UniqueConstraint("tenant_id", "event_id", "id", name="uq_registrations_event_id"),
        CheckConstraint("phone_e164 ~ '^\\+[1-9][0-9]{1,14}$'", name="ck_registrations_phone_e164"),
        CheckConstraint(
            "email::text = btrim(email::text) AND length(email::text) > 0",
            name="ck_registrations_email_trimmed",
        ),
        CheckConstraint("source IN ('self','bulk')", name="ck_registrations_source"),
        Index(
            "uq_registrations_email_active",
            "tenant_id",
            "event_id",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_registrations_phone_active",
            "tenant_id",
            "event_id",
            "phone_e164",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_registrations_external_ref",
            "tenant_id",
            "event_id",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref IS NOT NULL"),
        ),
        Index("ix_registrations_event_registered", "tenant_id", "event_id", "registered_at"),
    )


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    registration_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id", "registration_id"],
            ["registrations.tenant_id", "registrations.event_id", "registrations.id"],
            name="fk_tickets_registration",
        ),
        UniqueConstraint("tenant_id", "event_id", "id", name="uq_tickets_event_id"),
        UniqueConstraint("token_digest", name="uq_tickets_token_digest"),
        CheckConstraint("key_version > 0", name="ck_tickets_key_version"),
        CheckConstraint("status IN ('active','used','revoked')", name="ck_tickets_status"),
        Index(
            "uq_tickets_active_registration",
            "tenant_id",
            "event_id",
            "registration_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_tickets_event", "tenant_id", "event_id"),
    )


class EventSummary(Base):
    __tablename__ = "event_summary"
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    registered_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    checked_in_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    no_show_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    invalid_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_event_summary_event",
        ),
        CheckConstraint(
            "registered_count >= 0 AND checked_in_count >= 0 AND no_show_count >= 0 "
            "AND duplicate_count >= 0 AND invalid_count >= 0",
            name="ck_event_summary_counts",
        ),
    )


class PasswordCredential(Base):
    __tablename__ = "password_credentials"
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_auth_sessions_token_digest"),
        CheckConstraint("absolute_expires_at > created_at", name="ck_auth_sessions_absolute"),
        CheckConstraint("idle_expires_at <= absolute_expires_at", name="ck_auth_sessions_idle"),
        Index("ix_auth_sessions_user", "user_id", "revoked_at"),
    )


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    __table_args__ = (
        CheckConstraint("purpose IN ('mfa','enroll')", name="ck_auth_challenges_purpose"),
        UniqueConstraint("token_digest", name="uq_auth_challenges_token_digest"),
    )


class StaffInvitation(Base):
    __tablename__ = "staff_invitations"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    gate_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    invited_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    platform_actor_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    __table_args__ = (
        Index(
            "uq_initial_owner_pending",
            "tenant_id",
            unique=True,
            postgresql_where=text(
                "role='tenant_owner' AND platform_actor_id IS NOT NULL "
                "AND accepted_at IS NULL AND revoked_at IS NULL"
            ),
        ),
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_invitations_event",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "invited_by"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_invitations_inviter_member",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "event_id", "gate_id"],
            ["gates.tenant_id", "gates.event_id", "gates.id"],
            name="fk_invitations_gate",
        ),
        UniqueConstraint("token_digest", name="uq_staff_invitations_token_digest"),
        CheckConstraint(
            "gate_id IS NULL OR event_id IS NOT NULL", name="ck_invitations_gate_event"
        ),
        CheckConstraint(
            "(invited_by IS NOT NULL) <> (platform_actor_id IS NOT NULL)",
            name="ck_invitation_inviter_source",
        ),
        Index("ix_staff_invitations_tenant_email", "tenant_id", "email"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    __table_args__ = (UniqueConstraint("token_digest", name="uq_password_reset_tokens_digest"),)


class TotpCredential(Base):
    __tablename__ = "totp_credentials"
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accepted_step: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class MfaRecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    code_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (UniqueConstraint("code_digest", name="uq_mfa_recovery_codes_digest"),)


class EventAssignment(Base):
    __tablename__ = "event_assignments"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    gate_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_assignments_event",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_assignments_member",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "event_id", "gate_id"],
            ["gates.tenant_id", "gates.event_id", "gates.id"],
            name="fk_assignments_gate",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="ck_assignments_time"
        ),
        Index("ix_event_assignments_scope", "tenant_id", "user_id", "event_id", "gate_id"),
    )


class PlatformGrant(Base):
    __tablename__ = "platform_grants"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    __table_args__ = (
        CheckConstraint("valid_until > valid_from", name="ck_platform_grants_time"),
        Index("ix_platform_grants_user", "user_id", "operation"),
    )


class PlatformBootstrap(Base):
    __tablename__ = "platform_bootstrap"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    operator_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    email_verification_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    __table_args__ = (CheckConstraint("id=1", name="ck_platform_bootstrap_singleton"),)


class PlatformAuthChallenge(Base):
    __tablename__ = "platform_auth_challenges"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_platform_auth_challenges_token"),
        CheckConstraint("purpose IN ('mfa','enroll')", name="ck_platform_challenge_purpose"),
    )


class PlatformAuthSession(Base):
    __tablename__ = "platform_auth_sessions"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_platform_auth_sessions_token"),
        CheckConstraint("idle_expires_at <= absolute_expires_at", name="ck_platform_session_idle"),
        Index("ix_platform_auth_sessions_user", "user_id", "revoked_at"),
    )


class SecurityAuditEvent(Base):
    __tablename__ = "security_audit_events"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    tenant_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key_digest: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("attempts >= 0", name="ck_auth_rate_limits_attempts"),)


class JobRecord(Base):
    __tablename__ = "job_records"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    event_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    notification_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_job_records_event",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_job_records_tenant_id"),
        UniqueConstraint(
            "tenant_id", "job_type", "idempotency_key", name="uq_job_records_idempotency"
        ),
        CheckConstraint(
            "status IN ('pending','running','succeeded','retry_wait','dead')",
            name="ck_job_records_status",
        ),
        CheckConstraint("attempts >= 0 AND max_attempts BETWEEN 1 AND 20", name="ck_job_attempts"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_job_progress"),
        CheckConstraint(
            "(status = 'running') = (lease_token IS NOT NULL AND lease_until IS NOT NULL)",
            name="ck_job_running_lease",
        ),
        Index("ix_job_records_due", "status", "next_attempt_at", "created_at"),
        Index("ix_job_records_tenant_status", "tenant_id", "status", "created_at"),
    )


class DomainReconcileRequest(Base):
    __tablename__ = "domain_reconcile_requests"
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    domain_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["job_records.tenant_id", "job_records.id"],
            name="fk_domain_reconcile_job",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "domain_id"],
            ["tenant_domains.tenant_id", "tenant_domains.id"],
            name="fk_domain_reconcile_domain",
        ),
        Index("ix_domain_reconcile_tenant", "tenant_id", "domain_id"),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["job_records.tenant_id", "job_records.id"],
            name="fk_outbox_job",
        ),
        UniqueConstraint("job_id", name="uq_outbox_job"),
        CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
        CheckConstraint("(lease_token IS NULL) = (lease_until IS NULL)", name="ck_outbox_lease"),
        Index(
            "ix_outbox_unpublished",
            "next_attempt_at",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
        ),
        Index("ix_outbox_tenant", "tenant_id", "created_at"),
    )


class PrivateObject(Base):
    __tablename__ = "private_objects"
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    event_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    purpose: Mapped[str] = mapped_column(String(48), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    max_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_size_bytes: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["events.tenant_id", "events.id"],
            name="fk_private_objects_event",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_private_objects_tenant_id"),
        UniqueConstraint("object_key", name="uq_private_objects_key"),
        CheckConstraint(
            "status IN ('pending','available','delete_pending','deleted')",
            name="ck_private_objects_status",
        ),
        CheckConstraint(
            "max_size_bytes > 0 AND (actual_size_bytes IS NULL OR "
            "actual_size_bytes BETWEEN 0 AND max_size_bytes)",
            name="ck_private_objects_size",
        ),
        CheckConstraint("expires_at > created_at", name="ck_private_objects_expiry"),
        CheckConstraint(
            "purpose <> 'internal_test_artifact' OR "
            "(max_size_bytes <= 5242880 AND mime_type IN ('text/plain','application/pdf') "
            "AND expires_at <= created_at + interval '24 hours')",
            name="ck_private_objects_test_policy",
        ),
        Index(
            "ix_private_objects_expiring",
            "expires_at",
            postgresql_where=text("status <> 'deleted'"),
        ),
        Index("ix_private_objects_tenant", "tenant_id", "event_id", "status"),
    )
