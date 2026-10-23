"""M1-02 relational contract. Feature-specific tables follow their owning milestones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
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
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_tenant_domains_hostname"),
        Index("ix_tenant_domains_tenant", "tenant_id"),
        Index(
            "uq_tenant_domains_primary",
            "tenant_id",
            unique=True,
            postgresql_where=text(
                "is_primary AND verification_state = 'verified' AND tls_state = 'active'"
            ),
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
        CheckConstraint("role IN ('tenant_admin','gate_staff')", name="ck_tenant_memberships_role"),
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
    form_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    form_schema: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    pii_purge_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pii_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_events_tenant_id"),
        UniqueConstraint("tenant_id", "slug", name="uq_events_tenant_slug"),
        CheckConstraint("ends_at > starts_at", name="ck_events_time_order"),
        CheckConstraint("form_schema_version > 0", name="ck_events_form_version"),
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
