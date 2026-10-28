"""Platform notice approval boundaries against an isolated PostgreSQL database."""

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_events_postgres import owner
from test_tenancy_postgres import Harness

from app.core.config import Environment
from app.tenancy.domains import DomainDenied
from app.tenancy.privacy_notices import PrivacyNoticeDenied, PrivacyNotices

pytestmark = pytest.mark.postgres
pytest_plugins = ("test_tenancy_postgres",)


def test_platform_drafts_approves_and_activates_without_mutating_content(pg: Harness) -> None:
    tenant, _host, _session = owner(pg)
    notices = PrivacyNotices(pg.control, Environment.TEST)
    assert notices.list(pg.actor, tenant)["notices"] == []
    draft = notices.draft(pg.actor, tenant, "Approved synthetic test text", "test-basis", True)
    assert draft["version"] == 1
    assert draft["approved_at"] is None and draft["active"] is False
    with pytest.raises(PrivacyNoticeDenied, match="Approve"):
        notices.activate(pg.actor, tenant, 1)
    with pytest.raises(DomainDenied):
        notices.approve(uuid4(), tenant, 1, "test-approval-1")
    with pg.owner.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT sha256 FROM registration_notice_versions "
                    "WHERE tenant_id=:tenant AND version=1"
                ),
                {"tenant": tenant},
            )
            == hashlib.sha256(b"Approved synthetic test text").digest()
        )
    approved = notices.approve(pg.actor, tenant, 1, "test-approval-1")
    assert approved["approved_at"] and approved["approval_reference"] == "test-approval-1"
    active = notices.activate(pg.actor, tenant, 1)
    assert active["active"] is True
    assert notices.list(pg.actor, tenant)["notices"][0]["active"] is True
    with pg.owner.connect() as db:
        actions = [
            row[0]
            for row in db.execute(
                text("""SELECT action FROM security_audit_events
            WHERE tenant_id=:tenant AND action LIKE 'privacy.notice.%'"""),
                {"tenant": tenant},
            )
        ]
    assert set(actions) == {
        "privacy.notice.drafted",
        "privacy.notice.approved",
        "privacy.notice.activated",
    }


def test_test_only_notice_cannot_be_created_for_production(pg: Harness) -> None:
    tenant, _host, _session = owner(pg)
    notices = PrivacyNotices(pg.control, Environment.PRODUCTION)
    with pytest.raises(PrivacyNoticeDenied, match="restricted"):
        notices.draft(pg.actor, tenant, "Synthetic test text", "test-basis", True)
