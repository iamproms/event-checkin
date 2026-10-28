"""Platform-only, tenant-scoped notice drafting, approval, and activation."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from app.core.config import Environment
from app.db.models import RegistrationNoticeVersion, Tenant
from app.db.session import authorized_tenant_session
from app.tenancy.domains import DomainService


class PrivacyNoticeDenied(ValueError):
    pass


def _view(row: RegistrationNoticeVersion) -> dict[str, object]:
    return {
        "version": row.version,
        "body": row.body,
        "lawful_basis": row.lawful_basis,
        "test_only": row.test_only,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approval_reference": row.approval_reference,
        "active": row.active,
    }


class PrivacyNotices:
    def __init__(self, control_engine: Engine, environment: Environment) -> None:
        self.engine = control_engine
        self.environment = environment

    @staticmethod
    def _tenant(db: object, tenant_id: UUID) -> Tenant:
        from sqlalchemy.orm import Session

        assert isinstance(db, Session)
        tenant = db.get(Tenant, tenant_id, with_for_update=True)
        if tenant is None:
            raise PrivacyNoticeDenied("Organization unavailable")
        return tenant

    def list(self, actor: UUID, tenant_id: UUID) -> dict[str, object]:
        with authorized_tenant_session(self.engine, tenant_id) as db:
            DomainService._assert_platform_actor(db, actor)
            tenant = self._tenant(db, tenant_id)
            rows = db.scalars(
                select(RegistrationNoticeVersion)
                .where(RegistrationNoticeVersion.tenant_id == tenant_id)
                .order_by(RegistrationNoticeVersion.version.desc())
            ).all()
            return {
                "organization_id": str(tenant_id),
                "organization_name": tenant.name,
                "notices": [_view(row) for row in rows],
            }

    def draft(
        self, actor: UUID, tenant_id: UUID, body: str, lawful_basis: str, test_only: bool
    ) -> dict[str, object]:
        body, lawful_basis = body.strip(), lawful_basis.strip()
        if not 1 <= len(body) <= 20_000 or not 1 <= len(lawful_basis) <= 500:
            raise PrivacyNoticeDenied("Notice text and recorded lawful basis are required")
        if test_only and self.environment not in {Environment.LOCAL, Environment.TEST}:
            raise PrivacyNoticeDenied("Test notices are restricted to local and test environments")
        with authorized_tenant_session(self.engine, tenant_id) as db:
            DomainService._assert_platform_actor(db, actor)
            self._tenant(db, tenant_id)
            version = (
                db.scalar(
                    select(func.max(RegistrationNoticeVersion.version)).where(
                        RegistrationNoticeVersion.tenant_id == tenant_id
                    )
                )
                or 0
            ) + 1
            row = RegistrationNoticeVersion(
                tenant_id=tenant_id,
                version=version,
                body=body,
                lawful_basis=lawful_basis,
                sha256=hashlib.sha256(body.encode("utf-8")).digest(),
                created_by=actor,
                test_only=test_only,
                active=False,
            )
            db.add(row)
            DomainService._audit(
                db,
                actor,
                tenant_id,
                "privacy.notice.drafted",
                {"version": version, "test_only": test_only},
            )
            db.flush()
            return _view(row)

    def approve(
        self, actor: UUID, tenant_id: UUID, version: int, approval_reference: str
    ) -> dict[str, object]:
        reference = approval_reference.strip()
        if not 1 <= len(reference) <= 500:
            raise PrivacyNoticeDenied("Record an external approval reference")
        with authorized_tenant_session(self.engine, tenant_id) as db:
            DomainService._assert_platform_actor(db, actor)
            self._tenant(db, tenant_id)
            row = db.get(RegistrationNoticeVersion, (tenant_id, version), with_for_update=True)
            if row is None or row.approved_at is not None:
                raise PrivacyNoticeDenied("Notice draft is unavailable for approval")
            if hashlib.sha256(row.body.encode("utf-8")).digest() != row.sha256:
                raise PrivacyNoticeDenied("Notice content integrity check failed")
            row.approved_at = datetime.now(UTC)
            row.approved_by = actor
            row.approval_reference = reference
            DomainService._audit(
                db,
                actor,
                tenant_id,
                "privacy.notice.approved",
                {"version": version, "approval_reference": reference},
            )
            db.flush()
            return _view(row)

    def activate(self, actor: UUID, tenant_id: UUID, version: int) -> dict[str, object]:
        with authorized_tenant_session(self.engine, tenant_id) as db:
            DomainService._assert_platform_actor(db, actor)
            self._tenant(db, tenant_id)
            row = db.get(RegistrationNoticeVersion, (tenant_id, version), with_for_update=True)
            if row is None or row.approved_at is None:
                raise PrivacyNoticeDenied("Approve the notice before activation")
            if row.test_only and self.environment not in {Environment.LOCAL, Environment.TEST}:
                raise PrivacyNoticeDenied("Test notices cannot be activated here")
            if hashlib.sha256(row.body.encode("utf-8")).digest() != row.sha256:
                raise PrivacyNoticeDenied("Notice content integrity check failed")
            for current in db.scalars(
                select(RegistrationNoticeVersion)
                .where(
                    RegistrationNoticeVersion.tenant_id == tenant_id,
                    RegistrationNoticeVersion.active.is_(True),
                )
                .with_for_update()
            ):
                current.active = False
            db.flush()
            row.active = True
            DomainService._audit(
                db, actor, tenant_id, "privacy.notice.activated", {"version": version}
            )
            db.flush()
            return _view(row)
