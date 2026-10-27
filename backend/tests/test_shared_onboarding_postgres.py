"""Shared-host tenant creation, invitation, and membership isolation on real PostgreSQL."""

from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from test_tenancy_postgres import Harness

from app.tenancy.shared_host import shared_host_tenant
from app.tenancy.shared_onboarding import SharedOnboarding

pytestmark = pytest.mark.postgres
pytest_plugins = ("test_tenancy_postgres",)


def test_shared_onboarding_is_idempotent_and_invite_is_tenant_bound(pg: Harness) -> None:
    service = SharedOnboarding(pg.control, pg.email)
    key = uuid4()
    data = dict(
        actor=pg.actor, idempotency_key=key, name="Summit Operations",
        organizer_email="organizer@example.test", organizer_name="Event organizer",
        contact_phone=None, event_name="November event",
        origin="https://platform.local.example.test",
    )
    created = service.create(**data)
    assert created["invitation_delivery_status"] == "accepted_by_transport"
    assert service.create(**data) == created
    assert len(pg.email.links) == 1
    tenant_id = UUID(created["organization_id"])
    fragment = parse_qs(urlsplit(pg.email.links[0]).fragment)
    assert fragment["tenant"] == [str(tenant_id)]
    token = fragment["token"][0]
    with pg.owner.connect() as db:
        assert db.scalar(text("SELECT status FROM tenants WHERE id=:tenant"),
                         {"tenant": tenant_id}) == "active"
        assert db.scalar(text("SELECT count(*) FROM tenant_domains WHERE tenant_id=:tenant"),
                         {"tenant": tenant_id}) == 0
    state, challenge = pg.auth.accept_invitation(
        shared_host_tenant(tenant_id), token, "shared-organizer-password-123"
    )
    assert state == "enroll" and challenge
    # Password recovery applies after the required MFA enrollment activates membership.
    # This fixture advances only that membership state; MFA itself has separate tests.
    with pg.owner.begin() as db:
        db.execute(
            text("UPDATE tenant_memberships SET status='active', accepted_at=now() "
                 "WHERE tenant_id=:tenant"),
            {"tenant": tenant_id},
        )
    pg.auth.request_reset(
        shared_host_tenant(tenant_id), "organizer@example.test", "127.0.0.81",
        "https://platform.local.example.test", tenant_id,
    )
    reset_link = urlsplit(pg.email.links[-1])
    assert reset_link.netloc == "platform.local.example.test"
    reset_fragment = parse_qs(reset_link.fragment)
    assert reset_fragment["tenant"] == [str(tenant_id)]
    pg.auth.complete_reset(
        shared_host_tenant(tenant_id), reset_fragment["token"][0],
        "another-shared-organizer-password-123",
    )
    with pytest.raises(ValueError):
        pg.auth.accept_invitation(shared_host_tenant(tenant_id), token,
                                  "shared-organizer-password-123")
