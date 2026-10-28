"""Read-only organization directory for MFA-verified platform administrators."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.models import PlatformOnboardingRequest, Tenant
from app.tenancy.domains import DomainService


def _view(tenant: Tenant, onboarding: PlatformOnboardingRequest | None) -> dict[str, object]:
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "status": tenant.status,
        "created_at": tenant.created_at.isoformat(),
        "primary_organizer": onboarding.organizer_email if onboarding else None,
        "invitation_delivery_status": onboarding.delivery_status if onboarding else None,
    }


class PlatformOrganizations:
    def __init__(self, control_engine: Engine) -> None:
        self.engine = control_engine

    def list(
        self, actor: UUID, *, query: str = "", limit: int = 25, offset: int = 0
    ) -> dict[str, object]:
        search = query.strip()
        with Session(self.engine) as db, db.begin():
            DomainService._assert_platform_actor(db, actor)
            base = select(Tenant, PlatformOnboardingRequest).outerjoin(
                PlatformOnboardingRequest, PlatformOnboardingRequest.tenant_id == Tenant.id
            )
            if search:
                # Treat the user's search as literal text, including SQL wildcard characters.
                escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%"
                base = base.where(
                    or_(
                        Tenant.name.ilike(pattern, escape="\\"),
                        Tenant.slug.ilike(pattern, escape="\\"),
                        PlatformOnboardingRequest.organizer_email.ilike(pattern, escape="\\"),
                    )
                )
            total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
            rows = db.execute(
                base.order_by(Tenant.created_at.desc(), Tenant.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return {
                "organizations": [_view(tenant, onboarding) for tenant, onboarding in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(rows) < total,
            }

    def get(self, actor: UUID, tenant_id: UUID) -> dict[str, object] | None:
        with Session(self.engine) as db, db.begin():
            DomainService._assert_platform_actor(db, actor)
            row = db.execute(
                select(Tenant, PlatformOnboardingRequest)
                .outerjoin(
                    PlatformOnboardingRequest, PlatformOnboardingRequest.tenant_id == Tenant.id
                )
                .where(Tenant.id == tenant_id)
            ).one_or_none()
            return _view(*row) if row else None
