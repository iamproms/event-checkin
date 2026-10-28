"""Platform organization discovery against isolated PostgreSQL roles."""

from uuid import UUID, uuid4

import pytest
from test_tenancy_postgres import Harness

from app.tenancy.domains import DomainDenied
from app.tenancy.platform_organizations import PlatformOrganizations
from app.tenancy.shared_onboarding import SharedOnboarding

pytestmark = pytest.mark.postgres
pytest_plugins = ("test_tenancy_postgres",)


def test_directory_search_pagination_details_and_platform_grant(pg: Harness) -> None:
    onboarding = SharedOnboarding(pg.control, pg.email)
    created = [
        onboarding.create(
            actor=pg.actor,
            idempotency_key=uuid4(),
            name=name,
            organizer_email=email,
            organizer_name=None,
            contact_phone=None,
            event_name=None,
            origin="https://platform.local.example.test",
        )
        for name, email in (
            ("Directory Alpha", "alpha@example.test"),
            ("Directory Beta", "beta@example.test"),
        )
    ]
    directory = PlatformOrganizations(pg.control)
    first = directory.list(pg.actor, query="Directory", limit=1, offset=0)
    second = directory.list(pg.actor, query="Directory", limit=1, offset=1)
    assert first["total"] == second["total"] == 2
    assert first["has_more"] is True and second["has_more"] is False
    assert first["organizations"][0]["id"] != second["organizations"][0]["id"]
    assert {
        row["primary_organizer"] for page in (first, second) for row in page["organizations"]
    } == {"alpha@example.test", "beta@example.test"}
    assert directory.list(pg.actor, query="alpha@example.test")["total"] == 1
    assert directory.list(pg.actor, query="%_")["total"] == 0
    detail = directory.get(pg.actor, UUID(created[0]["organization_id"]))
    assert detail is not None
    assert detail["name"] == "Directory Alpha"
    assert detail["status"] == "active"
    assert detail["primary_organizer"] == "alpha@example.test"
    assert directory.get(pg.actor, uuid4()) is None
    with pytest.raises(DomainDenied):
        directory.list(uuid4(), query="Directory")
    with pytest.raises(DomainDenied):
        directory.get(uuid4(), UUID(created[0]["organization_id"]))
