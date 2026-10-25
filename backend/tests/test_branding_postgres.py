"""Branding publication and tenant boundaries against real PostgreSQL roles."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from test_events_postgres import owner
from test_tenancy_postgres import Harness

from app.auth.service import AuthDenied, Forbidden
from app.branding.service import BrandingConflict, BrandingService
from app.db.session import authorized_tenant_session

pytestmark = pytest.mark.postgres
pytest_plugins = ("test_tenancy_postgres",)


class MemoryStorage:
    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self.items[key] = data

    def get(self, key: str) -> bytes:
        return self.items[key]

    def delete(self, key: str) -> None:
        self.items.pop(key, None)


def logo() -> bytes:
    output = BytesIO()
    Image.new("RGB", (128, 128), "#46806a").save(output, format="PNG")
    return output.getvalue()


def test_publish_logo_restore_audit_and_tenant_isolation(pg: Harness) -> None:
    tenant_a, host_a, session_a = owner(pg)
    tenant_b, host_b, session_b = owner(pg)
    storage = MemoryStorage()
    service = BrandingService(pg.runtime, pg.auth, storage)
    assert service.public(host_a)["logo_url"] is None
    edited = service.save_draft(
        host_a,
        session_a,
        revision=0,
        display_name="Àjọ Events",
        primary_color="#46806A",
        accent_color="#46806A",
        sender_name="Àjọ Events",
    )
    with_logo = service.upload_logo(host_a, session_a, logo(), "image/png")
    assert with_logo["revision"] == edited["revision"] + 1
    assert all(key.startswith(f"retained/tenants/{tenant_a}/branding/") for key in storage.items)
    assert service.logo(host_a, session_a).startswith(b"\x89PNG")
    with pytest.raises((AuthDenied, Forbidden)):
        service.get_draft(host_a, session_b)
    first = service.publish(host_a, session_a, int(with_logo["revision"]))
    assert first["published_version"] == 1
    assert service.public(host_a)["display_name"] == "Àjọ Events"
    assert service.logo(host_a).startswith(b"\x89PNG")
    assert service.public(host_b)["logo_url"] is None
    removed = service.remove_logo(host_a, session_a)
    second = service.publish(host_a, session_a, int(removed["revision"]))
    assert second["published_version"] == 2
    assert service.public(host_a)["logo_url"] is None
    restored = service.restore(host_a, session_a, 1)
    assert restored["published_version"] == 3
    assert service.logo(host_a).startswith(b"\x89PNG")
    assert [row["version"] for row in service.history(host_a, session_a)] == [3, 2, 1]
    actions = [row["action"] for row in service.audit_history(host_a, session_a)]
    assert "branding.published" in actions and "branding.restored" in actions
    with authorized_tenant_session(pg.runtime, tenant_a) as db:
        assert db.scalar(text("SELECT count(*) FROM tenant_branding_versions")) == 3
        assert db.scalar(text("SELECT count(*) FROM tenant_branding_audit")) >= 6
        profile = db.execute(text("SELECT id,name FROM current_active_tenant_profile()"))
        assert profile.one().id == tenant_a
    with pytest.raises(ProgrammingError):
        with authorized_tenant_session(pg.runtime, tenant_a) as db:
            db.execute(text("SELECT * FROM tenants"))
    with pytest.raises(ProgrammingError):
        with authorized_tenant_session(pg.runtime, tenant_a) as db:
            db.execute(text("UPDATE tenant_branding_versions SET display_name='Tampered'"))
    with authorized_tenant_session(pg.runtime, tenant_b) as db:
        assert db.scalar(text("SELECT count(*) FROM tenant_branding_versions")) == 0
    with pg.owner.connect() as db:
        tenant_b_actor = db.scalar(
            text("SELECT user_id FROM tenant_memberships WHERE tenant_id=:tenant LIMIT 1"),
            {"tenant": tenant_b},
        )
    with pytest.raises(IntegrityError):
        with authorized_tenant_session(pg.runtime, tenant_a) as db:
            db.execute(
                text("""INSERT INTO tenant_branding_audit
                (tenant_id,actor_user_id,action,metadata)
                VALUES (:tenant,:actor,'branding.forged','{}')"""),
                {"tenant": tenant_a, "actor": tenant_b_actor},
            )


def test_concurrent_publish_serializes_on_tenant_row(pg: Harness) -> None:
    tenant, host, session = owner(pg)
    service = BrandingService(pg.runtime, pg.auth, MemoryStorage())
    draft = service.save_draft(
        host,
        session,
        revision=0,
        display_name="Race",
        primary_color="#46806A",
        accent_color="#46806A",
        sender_name="Race",
    )

    def publish() -> bool:
        try:
            service.publish(host, session, int(draft["revision"]))
            return True
        except BrandingConflict:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: publish(), range(2))) == [False, True]
    with authorized_tenant_session(pg.runtime, tenant) as db:
        assert db.scalar(text("SELECT count(*) FROM tenant_branding_versions")) == 1
