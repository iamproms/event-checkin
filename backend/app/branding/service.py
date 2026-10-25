"""Versioned tenant branding with tenant-scoped storage and attributable changes."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.service import AuthService
from app.branding.assets import AssetInvalid, BrandingStorage, sanitize_logo
from app.branding.contrast import action_text, validate_brand_color
from app.db.models import (
    PrivateObject,
    TenantBranding,
    TenantBrandingAudit,
    TenantBrandingDraft,
    TenantBrandingVersion,
)
from app.db.session import authorized_tenant_session, tenant_session_for_domain


class BrandingInvalid(ValueError):
    pass


class BrandingConflict(ValueError):
    pass


def clean_label(value: str, name: str, limit: int) -> str:
    clean = value.strip()
    if (
        not 1 <= len(clean) <= limit
        or any(ord(char) < 32 for char in clean)
        or any(char in "<>" for char in clean)
    ):
        raise BrandingInvalid(f"{name} must be 1–{limit} plain-text characters.")
    return clean


def _asset_id(key: str | None) -> UUID | None:
    if not key:
        return None
    try:
        return UUID(key.rsplit("/", 1)[-1])
    except ValueError:
        return None


def _view(
    *,
    display_name: str,
    logo_object_key: str | None,
    primary_color: str | None,
    accent_color: str | None,
    sender_name: str | None,
    revision: int,
    logo_url: str,
) -> dict[str, object]:
    return {
        "display_name": display_name,
        "logo_url": logo_url if logo_object_key else None,
        "primary_color": primary_color,
        "accent_color": accent_color,
        "action_text_color": action_text(primary_color) if primary_color else None,
        "sender_name": sender_name,
        "revision": revision,
    }


class BrandingService:
    def __init__(self, engine: Engine, auth: AuthService, storage: BrandingStorage) -> None:
        self.engine = engine
        self.auth = auth
        self.storage = storage

    def _scope(self, host: str, session_token: str) -> tuple[UUID, UUID]:
        tenant_id = self.auth.authorize(host, session_token, "tenant.settings")
        actor, _, _ = self.auth.current(host, session_token)
        return tenant_id, actor.id

    @staticmethod
    def _tenant_profile(db: Session, *, lock: bool = False) -> tuple[UUID, str]:
        if lock:
            # The base tenant table is intentionally not readable by the runtime
            # role. Serialize branding publication with a transaction-scoped
            # advisory lock derived from the already-authorized tenant context.
            db.execute(
                text("""SELECT pg_advisory_xact_lock(
                  hashtextextended(current_setting('app.tenant_id'), 0))""")
            )
        row = db.execute(text("SELECT id,name FROM current_active_tenant_profile()"))
        profile = row.one_or_none()
        if profile is None:
            raise BrandingInvalid("Tenant is unavailable.")
        return profile.id, profile.name

    @staticmethod
    def _audit(
        db: Session, tenant_id: UUID, actor_id: UUID, action: str, version: int | None = None
    ) -> None:
        db.add(
            TenantBrandingAudit(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action=action,
                version=version,
                metadata_json={},
            )
        )

    @staticmethod
    def _draft(
        db: Session, tenant_id: UUID, tenant_name: str, actor_id: UUID
    ) -> TenantBrandingDraft:
        draft = db.scalar(
            select(TenantBrandingDraft)
            .where(TenantBrandingDraft.tenant_id == tenant_id)
            .with_for_update()
        )
        if draft is not None:
            return draft
        current = db.get(TenantBranding, tenant_id)
        draft = TenantBrandingDraft(
            tenant_id=tenant_id,
            revision=0,
            display_name=(
                current.display_name if current and current.display_name else tenant_name
            ),
            logo_object_key=current.logo_object_key if current else None,
            primary_color=current.primary_color if current else None,
            accent_color=current.accent_color if current else None,
            sender_name=current.sender_name if current else None,
            updated_by=actor_id,
        )
        db.add(draft)
        db.flush()
        return draft

    def get_draft(self, host: str, session_token: str) -> dict[str, object]:
        tenant_id, _ = self._scope(host, session_token)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            _, tenant_name = self._tenant_profile(db)
            draft = db.get(TenantBrandingDraft, tenant_id)
            current = db.get(TenantBranding, tenant_id)
            if draft:
                view = _view(
                    display_name=draft.display_name or tenant_name,
                    logo_object_key=draft.logo_object_key,
                    primary_color=draft.primary_color,
                    accent_color=draft.accent_color,
                    sender_name=draft.sender_name,
                    revision=draft.revision,
                    logo_url="/api/v1/branding/draft/logo",
                )
            else:
                view = _view(
                    display_name=(
                        current.display_name if current and current.display_name else tenant_name
                    ),
                    logo_object_key=current.logo_object_key if current else None,
                    primary_color=current.primary_color if current else None,
                    accent_color=current.accent_color if current else None,
                    sender_name=current.sender_name if current else None,
                    revision=0,
                    logo_url="/api/v1/branding/draft/logo",
                )
            view["published_version"] = current.published_version if current else None
            return view

    def save_draft(
        self,
        host: str,
        session_token: str,
        *,
        revision: int,
        display_name: str,
        primary_color: str | None,
        accent_color: str | None,
        sender_name: str,
    ) -> dict[str, object]:
        name = clean_label(display_name, "Display name", 120)
        sender = clean_label(sender_name, "Sender display name", 100)
        primary = validate_brand_color(primary_color, "Primary color")
        accent = validate_brand_color(accent_color, "Accent color")
        tenant_id, actor_id = self._scope(host, session_token)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            _, tenant_name = self._tenant_profile(db, lock=True)
            draft = self._draft(db, tenant_id, tenant_name, actor_id)
            if draft.revision != revision:
                raise BrandingConflict("Branding changed. Refresh before saving.")
            draft.display_name = name
            draft.primary_color = primary
            draft.accent_color = accent
            draft.sender_name = sender
            draft.updated_by = actor_id
            draft.updated_at = datetime.now(UTC)
            draft.revision += 1
            self._audit(db, tenant_id, actor_id, "branding.draft.saved")
        return self.get_draft(host, session_token)

    def upload_logo(
        self, host: str, session_token: str, data: bytes, declared_mime: str
    ) -> dict[str, object]:
        tenant_id, actor_id = self._scope(host, session_token)
        # Authenticate and authorize before spending CPU on untrusted image
        # decoding. The API has already bounded the request body size.
        raster = sanitize_logo(data, declared_mime)
        object_id = uuid4()
        # M1-04's local orphan lifecycle intentionally expires `tenants/` test
        # artifacts after one day. Published branding uses a separate retained,
        # still tenant-scoped prefix so version history does not lose its logo.
        key = f"retained/tenants/{tenant_id}/branding/logos/{object_id}"
        self.storage.put(key, raster)
        try:
            with authorized_tenant_session(self.engine, tenant_id) as db:
                _, tenant_name = self._tenant_profile(db, lock=True)
                draft = self._draft(db, tenant_id, tenant_name, actor_id)
                db.add(
                    PrivateObject(
                        id=object_id,
                        tenant_id=tenant_id,
                        purpose="branding_logo",
                        object_key=key,
                        status="available",
                        mime_type="image/png",
                        max_size_bytes=len(raster),
                        actual_size_bytes=len(raster),
                        expires_at=datetime.now(UTC) + timedelta(days=36_500),
                        completed_at=datetime.now(UTC),
                    )
                )
                draft.logo_object_key = key
                draft.updated_by = actor_id
                draft.updated_at = datetime.now(UTC)
                draft.revision += 1
                self._audit(db, tenant_id, actor_id, "branding.logo.uploaded")
        except Exception:
            self.storage.delete(key)
            raise
        return self.get_draft(host, session_token)

    def remove_logo(self, host: str, session_token: str) -> dict[str, object]:
        tenant_id, actor_id = self._scope(host, session_token)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            _, tenant_name = self._tenant_profile(db, lock=True)
            draft = self._draft(db, tenant_id, tenant_name, actor_id)
            draft.logo_object_key = None
            draft.updated_by = actor_id
            draft.updated_at = datetime.now(UTC)
            draft.revision += 1
            self._audit(db, tenant_id, actor_id, "branding.logo.removed")
        return self.get_draft(host, session_token)

    @staticmethod
    def _validate_logo(db: Session, tenant_id: UUID, key: str | None) -> None:
        if key is None:
            return
        object_id = _asset_id(key)
        obj = db.scalar(
            select(PrivateObject).where(
                PrivateObject.tenant_id == tenant_id,
                PrivateObject.id == object_id,
                PrivateObject.object_key == key,
                PrivateObject.purpose == "branding_logo",
                PrivateObject.status == "available",
            )
        )
        if obj is None or obj.expires_at <= datetime.now(UTC):
            raise BrandingInvalid("Logo is unavailable. Upload it again.")

    @staticmethod
    def _publish_row(
        db: Session,
        tenant_id: UUID,
        actor_id: UUID,
        *,
        display_name: str,
        logo_object_key: str | None,
        primary_color: str | None,
        accent_color: str | None,
        sender_name: str | None,
        restored_from_version: int | None,
    ) -> int:
        current = db.get(TenantBranding, tenant_id)
        next_version = (current.published_version or 0) + 1 if current else 1
        db.add(
            TenantBrandingVersion(
                tenant_id=tenant_id,
                version=next_version,
                display_name=display_name,
                logo_object_key=logo_object_key,
                primary_color=primary_color,
                accent_color=accent_color,
                sender_name=sender_name,
                published_by=actor_id,
                restored_from_version=restored_from_version,
            )
        )
        if current is None:
            current = TenantBranding(tenant_id=tenant_id)
            db.add(current)
        current.published_version = next_version
        current.display_name = display_name
        current.logo_object_key = logo_object_key
        current.primary_color = primary_color
        current.accent_color = accent_color
        current.sender_name = sender_name
        current.updated_at = datetime.now(UTC)
        return next_version

    def publish(self, host: str, session_token: str, revision: int) -> dict[str, object]:
        tenant_id, actor_id = self._scope(host, session_token)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            _, tenant_name = self._tenant_profile(db, lock=True)
            draft = self._draft(db, tenant_id, tenant_name, actor_id)
            if draft.revision != revision:
                raise BrandingConflict("Branding changed. Refresh before publishing.")
            validate_brand_color(draft.primary_color, "Primary color")
            validate_brand_color(draft.accent_color, "Accent color")
            self._validate_logo(db, tenant_id, draft.logo_object_key)
            version = self._publish_row(
                db,
                tenant_id,
                actor_id,
                display_name=clean_label(draft.display_name or "", "Display name", 120),
                logo_object_key=draft.logo_object_key,
                primary_color=draft.primary_color,
                accent_color=draft.accent_color,
                sender_name=clean_label(draft.sender_name, "Sender display name", 100)
                if draft.sender_name
                else None,
                restored_from_version=None,
            )
            draft.revision += 1
            draft.updated_by = actor_id
            draft.updated_at = datetime.now(UTC)
            self._audit(db, tenant_id, actor_id, "branding.published", version)
        return self.get_draft(host, session_token)

    def restore(self, host: str, session_token: str, source_version: int) -> dict[str, object]:
        tenant_id, actor_id = self._scope(host, session_token)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            _, tenant_name = self._tenant_profile(db, lock=True)
            previous = db.get(TenantBrandingVersion, (tenant_id, source_version))
            if previous is None:
                raise BrandingInvalid("Branding version is unavailable.")
            validate_brand_color(previous.primary_color, "Primary color")
            validate_brand_color(previous.accent_color, "Accent color")
            self._validate_logo(db, tenant_id, previous.logo_object_key)
            next_version = self._publish_row(
                db,
                tenant_id,
                actor_id,
                display_name=clean_label(previous.display_name or "", "Display name", 120),
                logo_object_key=previous.logo_object_key,
                primary_color=previous.primary_color,
                accent_color=previous.accent_color,
                sender_name=previous.sender_name,
                restored_from_version=source_version,
            )
            draft = self._draft(db, tenant_id, tenant_name, actor_id)
            draft.display_name = previous.display_name
            draft.logo_object_key = previous.logo_object_key
            draft.primary_color = previous.primary_color
            draft.accent_color = previous.accent_color
            draft.sender_name = previous.sender_name
            draft.revision += 1
            draft.updated_by = actor_id
            draft.updated_at = datetime.now(UTC)
            self._audit(db, tenant_id, actor_id, "branding.restored", next_version)
        return self.get_draft(host, session_token)

    def history(self, host: str, session_token: str) -> list[dict[str, object]]:
        tenant_id, _ = self._scope(host, session_token)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            rows = db.scalars(
                select(TenantBrandingVersion)
                .where(TenantBrandingVersion.tenant_id == tenant_id)
                .order_by(TenantBrandingVersion.version.desc())
                .limit(50)
            ).all()
            return [
                {
                    "version": row.version,
                    "display_name": row.display_name or "",
                    "published_at": row.published_at.isoformat(),
                    "restored_from_version": row.restored_from_version,
                    "has_logo": row.logo_object_key is not None,
                }
                for row in rows
            ]

    def audit_history(self, host: str, session_token: str) -> list[dict[str, object]]:
        tenant_id, _ = self._scope(host, session_token)
        with authorized_tenant_session(self.engine, tenant_id) as db:
            rows = db.scalars(
                select(TenantBrandingAudit)
                .where(TenantBrandingAudit.tenant_id == tenant_id)
                .order_by(TenantBrandingAudit.occurred_at.desc(), TenantBrandingAudit.id.desc())
                .limit(50)
            ).all()
            return [
                {
                    "action": row.action,
                    "version": row.version,
                    "actor_user_id": str(row.actor_user_id),
                    "occurred_at": row.occurred_at.isoformat(),
                }
                for row in rows
            ]

    def public(self, trusted_host: str) -> dict[str, object]:
        with tenant_session_for_domain(self.engine, trusted_host) as db:
            tenant_id, tenant_name = self._tenant_profile(db)
            current = db.get(TenantBranding, tenant_id)
            if current is None or current.published_version is None:
                return _view(
                    display_name=tenant_name,
                    logo_object_key=None,
                    primary_color=None,
                    accent_color=None,
                    sender_name=None,
                    revision=0,
                    logo_url="/api/v1/branding/public/logo",
                )
            return _view(
                display_name=current.display_name or tenant_name,
                logo_object_key=current.logo_object_key,
                primary_color=current.primary_color,
                accent_color=current.accent_color,
                sender_name=current.sender_name,
                revision=current.published_version,
                logo_url=f"/api/v1/branding/public/logo?v={current.published_version}",
            )

    def logo(self, trusted_host: str, session_token: str | None = None) -> bytes:
        if session_token is None:
            with tenant_session_for_domain(self.engine, trusted_host) as db:
                tenant_id, _ = self._tenant_profile(db)
                current = db.get(TenantBranding, tenant_id)
                key = current.logo_object_key if current and current.published_version else None
                self._validate_logo(db, tenant_id, key)
        else:
            tenant_id, _ = self._scope(trusted_host, session_token)
            with authorized_tenant_session(self.engine, tenant_id) as db:
                draft = db.get(TenantBrandingDraft, tenant_id)
                key = draft.logo_object_key if draft else None
                self._validate_logo(db, tenant_id, key)
        if key is None:
            raise BrandingInvalid("Logo is unavailable.")
        try:
            return self.storage.get(key)
        except (OSError, AssetInvalid) as exc:
            raise BrandingInvalid("Logo is unavailable.") from exc
