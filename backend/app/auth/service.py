"""Server-side staff identity and session operations."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.corpus import CompromisedPasswordCorpus
from app.auth.email import DeliveryUnavailable, DisabledEmailDelivery, EmailDelivery
from app.auth.policy import Assignment, permits, requires_mfa, session_lifetime
from app.auth.security import (
    accepted_totp_step,
    decrypt_totp,
    encrypt_totp,
    hash_password,
    new_token,
    new_totp_secret,
    recovery_codes,
    token_digest,
    verify_password,
)
from app.core.config import Settings
from app.db.models import (
    AuthChallenge,
    AuthRateLimit,
    AuthSession,
    EventAssignment,
    MfaRecoveryCode,
    PasswordCredential,
    PasswordResetToken,
    SecurityAuditEvent,
    StaffInvitation,
    TenantMembership,
    TotpCredential,
    User,
)
from app.db.session import normalize_hostname


class AuthDenied(ValueError):
    pass


class Forbidden(AuthDenied):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        corpus: CompromisedPasswordCorpus,
        email: EmailDelivery,
    ) -> None:
        self.engine, self.settings, self.corpus, self.email = engine, settings, corpus, email

    def _tenant(self, db: Session, hostname: str) -> UUID:
        host = normalize_hostname(hostname)
        tenant = db.execute(
            text("SELECT resolve_active_tenant_domain(:host)"), {"host": host}
        ).scalar_one_or_none()
        if not isinstance(tenant, UUID):
            raise AuthDenied("Unauthorized")
        # Identity-role access is limited to memberships, assignments and invitations.
        # The tenant runtime connection is never opened until membership succeeds.
        db.execute(text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant)})
        return tenant

    @staticmethod
    def _member(db: Session, tenant: UUID, user: UUID) -> TenantMembership:
        member = db.get(TenantMembership, (tenant, user))
        if member is None or member.status != "active":
            raise AuthDenied("Unauthorized")
        return member

    @staticmethod
    def _audit(
        db: Session,
        action: str,
        user: UUID | None,
        tenant: UUID | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        db.add(
            SecurityAuditEvent(
                actor_user_id=user,
                tenant_id=tenant,
                action=action,
                metadata_json=metadata or {},
            )
        )

    @staticmethod
    def _limit(db: Session, key: str, now: datetime, ceiling: int = 5) -> None:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        row = db.get(AuthRateLimit, digest, with_for_update=True)
        if row is None:
            db.add(AuthRateLimit(key_digest=digest, attempts=1, window_started_at=now))
            return
        if row.blocked_until is not None and row.blocked_until > now:
            raise AuthDenied("Too many attempts; try again later")
        if row.window_started_at <= now - timedelta(minutes=15):
            row.attempts, row.window_started_at, row.blocked_until = 1, now, None
        else:
            row.attempts += 1
            if row.attempts >= ceiling:
                row.blocked_until = now + timedelta(minutes=15)

    @staticmethod
    def _check_limit(db: Session, key: str, now: datetime) -> None:
        row = db.get(AuthRateLimit, hashlib.sha256(key.encode("utf-8")).digest())
        if row and row.blocked_until and row.blocked_until > now:
            raise AuthDenied("Too many attempts; try again later")

    @staticmethod
    def _clear_limit(db: Session, key: str) -> None:
        row = db.get(AuthRateLimit, hashlib.sha256(key.encode("utf-8")).digest())
        if row:
            row.attempts, row.blocked_until = 0, None

    @staticmethod
    def _session(db: Session, user: UUID, tenant: UUID, role: str, mfa: bool) -> str:
        now = utcnow()
        idle, absolute = session_lifetime(role)
        raw = new_token()
        db.add(
            AuthSession(
                user_id=user,
                tenant_id=tenant,
                token_digest=token_digest(raw),
                last_seen_at=now,
                idle_expires_at=now + idle,
                absolute_expires_at=now + absolute,
                mfa_verified_at=now if mfa else None,
            )
        )
        AuthService._audit(db, "session.created", user, tenant)
        return raw

    def login(self, hostname: str, email: str, password: str, ip: str) -> tuple[str, str]:
        keys: list[str] = []
        try:
            with Session(self.engine) as db, db.begin():
                tenant = self._tenant(db, hostname)
                keys = [f"login:account:{tenant}:{email.casefold()}", f"login:ip:{tenant}:{ip}"]
                for key in keys:
                    self._check_limit(db, key, utcnow())
            result = self._login_inner(hostname, email, password)
            with Session(self.engine) as db, db.begin():
                self._tenant(db, hostname)
                for key in keys:
                    self._clear_limit(db, key)
            return result
        except AuthDenied:
            try:
                with Session(self.engine) as db, db.begin():
                    tenant = self._tenant(db, hostname)
                    for key in keys:
                        self._limit(db, key, utcnow(), 5 if ":account:" in key else 20)
                    self._audit(db, "authentication.failed", None, tenant)
            except AuthDenied:
                pass
            raise

    def _login_inner(self, hostname: str, email: str, password: str) -> tuple[str, str]:
        now = utcnow()
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            user = db.scalar(select(User).where(User.email == email.strip()))
            credential = db.get(PasswordCredential, user.id) if user else None
            if not verify_password(credential.password_hash if credential else None, password):
                raise AuthDenied("Invalid credentials")
            assert user is not None
            if user.status != "active":
                raise AuthDenied("Invalid credentials")
            member = self._member(db, tenant, user.id)
            if requires_mfa(member.role):
                totp = db.get(TotpCredential, user.id)
                purpose = "mfa" if totp and totp.confirmed_at else "enroll"
                raw = new_token()
                db.add(
                    AuthChallenge(
                        user_id=user.id,
                        tenant_id=tenant,
                        token_digest=token_digest(raw),
                        purpose=purpose,
                        expires_at=now + timedelta(minutes=5),
                    )
                )
                self._audit(db, "authentication.password_verified", user.id, tenant)
                return purpose, raw
            self._audit(db, "authentication.succeeded", user.id, tenant)
            return "session", self._session(db, user.id, tenant, member.role, False)

    def _challenge(self, db: Session, raw: str, tenant: UUID) -> AuthChallenge:
        challenge = db.scalar(
            select(AuthChallenge)
            .where(AuthChallenge.token_digest == token_digest(raw))
            .with_for_update()
        )
        if (
            challenge is None
            or challenge.tenant_id != tenant
            or challenge.consumed_at is not None
            or challenge.expires_at <= utcnow()
        ):
            raise AuthDenied("Authentication challenge expired")
        return challenge

    def enroll_totp(self, hostname: str, challenge_token: str) -> str:
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            challenge = self._challenge(db, challenge_token, tenant)
            if challenge.purpose != "enroll":
                raise AuthDenied("Invalid enrollment state")
            existing = db.get(TotpCredential, challenge.user_id)
            if existing and existing.confirmed_at:
                raise AuthDenied("MFA already enrolled")
            key = self._encryption_key()
            secret = new_totp_secret()
            if existing:
                existing.encrypted_secret = encrypt_totp(secret, key, str(challenge.user_id))
                existing.key_id = self.settings.auth_key_id
            else:
                db.add(
                    TotpCredential(
                        user_id=challenge.user_id,
                        encrypted_secret=encrypt_totp(secret, key, str(challenge.user_id)),
                        key_id=self.settings.auth_key_id,
                    )
                )
            return secret

    def _encryption_key(self) -> bytes:
        encoded = self.settings.auth_encryption_key
        if encoded is None:
            raise AuthDenied("MFA encryption key is unavailable")
        try:
            key = base64.b64decode(encoded.get_secret_value(), validate=True)
        except ValueError as exc:
            raise AuthDenied("MFA encryption key is invalid") from exc
        if len(key) != 32:
            raise AuthDenied("MFA encryption key is invalid")
        return key

    def verify_mfa(
        self,
        hostname: str,
        challenge_token: str,
        code: str,
        recovery: bool = False,
        ip: str = "unknown",
    ) -> tuple[str, list[str]]:
        try:
            return self._verify_mfa_inner(hostname, challenge_token, code, recovery, ip)
        except AuthDenied:
            try:
                with Session(self.engine) as db, db.begin():
                    tenant = self._tenant(db, hostname)
                    self._audit(db, "mfa.failed", None, tenant)
            except AuthDenied:
                pass
            raise

    def _verify_mfa_inner(
        self, hostname: str, challenge_token: str, code: str, recovery: bool, ip: str
    ) -> tuple[str, list[str]]:
        with Session(self.engine) as limiter, limiter.begin():
            tenant = self._tenant(limiter, hostname)
            challenge_for_limit = self._challenge(limiter, challenge_token, tenant)
            self._limit(
                limiter,
                f"mfa:account:{tenant}:{challenge_for_limit.user_id}",
                utcnow(),
            )
            self._limit(limiter, f"mfa:ip:{tenant}:{ip}", utcnow(), 20)
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            challenge = self._challenge(db, challenge_token, tenant)
            member = db.get(TenantMembership, (tenant, challenge.user_id))
            if member is None or member.status not in {"active", "pending_mfa"}:
                raise AuthDenied("Unauthorized")
            totp = db.get(TotpCredential, challenge.user_id, with_for_update=True)
            if totp is None or totp.key_id != self.settings.auth_key_id:
                raise AuthDenied("MFA is unavailable")
            issued_codes: list[str] = []
            if recovery:
                if challenge.purpose != "mfa":
                    raise AuthDenied("Invalid MFA method")
                code_row = db.scalar(
                    select(MfaRecoveryCode)
                    .where(
                        MfaRecoveryCode.user_id == challenge.user_id,
                        MfaRecoveryCode.code_digest == token_digest(code),
                        MfaRecoveryCode.used_at.is_(None),
                    )
                    .with_for_update()
                )
                if code_row is None:
                    raise AuthDenied("Invalid MFA code")
                code_row.used_at = utcnow()
                self._audit(db, "mfa.recovery_used", challenge.user_id, tenant)
            else:
                secret = decrypt_totp(
                    totp.encrypted_secret, self._encryption_key(), str(challenge.user_id)
                )
                step = accepted_totp_step(secret, code, totp.last_accepted_step)
                if step is None:
                    raise AuthDenied("Invalid MFA code")
                totp.last_accepted_step = step
            if challenge.purpose == "enroll":
                totp.confirmed_at = utcnow()
                for raw in recovery_codes():
                    issued_codes.append(raw)
                    db.add(
                        MfaRecoveryCode(user_id=challenge.user_id, code_digest=token_digest(raw))
                    )
                if member.status == "pending_mfa":
                    member.status, member.accepted_at = "active", utcnow()
                self._audit(db, "mfa.enrolled", challenge.user_id, tenant)
            elif totp.confirmed_at is None:
                raise AuthDenied("MFA enrollment incomplete")
            elif member.status == "pending_mfa":
                member.status, member.accepted_at = "active", utcnow()
            challenge.consumed_at = utcnow()
            db.execute(
                update(AuthSession)
                .where(
                    AuthSession.user_id == challenge.user_id,
                    AuthSession.tenant_id == tenant,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=utcnow())
            )
            self._audit(db, "authentication.succeeded", challenge.user_id, tenant)
            self._clear_limit(db, f"mfa:account:{tenant}:{challenge.user_id}")
            self._clear_limit(db, f"mfa:ip:{tenant}:{ip}")
            return self._session(db, challenge.user_id, tenant, member.role, True), issued_codes

    def current(self, hostname: str, raw: str) -> tuple[User, TenantMembership, AuthSession]:
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            session = db.scalar(
                select(AuthSession)
                .where(AuthSession.token_digest == token_digest(raw))
                .with_for_update()
            )
            now = utcnow()
            if (
                session is None
                or session.tenant_id != tenant
                or session.revoked_at is not None
                or session.idle_expires_at <= now
                or session.absolute_expires_at <= now
            ):
                raise AuthDenied("Session expired")
            user = db.get(User, session.user_id)
            if user is None or user.status != "active":
                raise AuthDenied("Session expired")
            member = self._member(db, tenant, user.id)
            if requires_mfa(member.role) and session.mfa_verified_at is None:
                raise AuthDenied("MFA required")
            idle, absolute = session_lifetime(member.role)
            if session.created_at + absolute <= now:
                raise AuthDenied("Session expired")
            session.last_seen_at = now
            session.idle_expires_at = min(now + idle, session.absolute_expires_at)
            db.expunge(user)
            db.expunge(member)
            db.expunge(session)
            return user, member, session

    def logout(self, raw: str) -> None:
        with Session(self.engine) as db, db.begin():
            session = db.scalar(
                select(AuthSession)
                .where(AuthSession.token_digest == token_digest(raw))
                .with_for_update()
            )
            if session and session.revoked_at is None:
                session.revoked_at = utcnow()
                self._audit(db, "session.revoked", session.user_id, session.tenant_id)

    def cancel_challenge(self, raw: str) -> None:
        with Session(self.engine) as db, db.begin():
            challenge = db.scalar(
                select(AuthChallenge)
                .where(AuthChallenge.token_digest == token_digest(raw))
                .with_for_update()
            )
            if challenge and challenge.consumed_at is None:
                challenge.consumed_at = utcnow()

    def authorize(
        self,
        hostname: str,
        raw: str,
        permission: str,
        event_id: UUID | None = None,
        gate_id: UUID | None = None,
    ) -> UUID:
        user, _, _ = self.current(hostname, raw)
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            member = self._member(db, tenant, user.id)
            live_session = db.scalar(
                select(AuthSession).where(AuthSession.token_digest == token_digest(raw))
            )
            if (
                live_session is None
                or live_session.revoked_at is not None
                or live_session.tenant_id != tenant
                or live_session.idle_expires_at <= utcnow()
                or live_session.absolute_expires_at <= utcnow()
                or (requires_mfa(member.role) and live_session.mfa_verified_at is None)
            ):
                raise AuthDenied("Session expired")
            rows = db.scalars(
                select(EventAssignment).where(
                    EventAssignment.tenant_id == tenant,
                    EventAssignment.user_id == user.id,
                )
            ).all()
            assignments = [
                Assignment(
                    item.event_id, item.gate_id, item.valid_from, item.valid_until, item.revoked_at
                )
                for item in rows
            ]
            if not permits(member.role, permission, assignments, utcnow(), event_id, gate_id):
                raise Forbidden("Permission denied")
            return tenant

    def revoke_tenant_membership(self, hostname: str, raw_session: str, target: UUID) -> None:
        tenant = self.authorize(hostname, raw_session, "staff.manage")
        actor, _, _ = self.current(hostname, raw_session)
        with Session(self.engine) as db, db.begin():
            self._tenant(db, hostname)
            member = db.scalar(
                select(TenantMembership)
                .where(
                    TenantMembership.tenant_id == tenant,
                    TenantMembership.user_id == target,
                )
                .with_for_update()
            )
            if member is None or member.status != "active":
                raise AuthDenied("Membership unavailable")
            member.status = "revoked"
            db.execute(
                update(AuthSession)
                .where(
                    AuthSession.user_id == target,
                    AuthSession.tenant_id == tenant,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=utcnow())
            )
            self._audit(db, "membership.revoked", actor.id, tenant, {"target_user_id": str(target)})

    def issue_invitation(
        self,
        hostname: str,
        raw_session: str,
        email: str,
        role: str,
        event_id: UUID | None,
        gate_id: UUID | None,
    ) -> None:
        if isinstance(self.email, DisabledEmailDelivery):
            raise DeliveryUnavailable("Transactional email delivery is not configured")
        base_url = self._base_url(hostname)
        tenant = self.authorize(hostname, raw_session, "invitation.issue")
        actor, actor_member, _ = self.current(hostname, raw_session)
        delegate_roles = {
            "tenant_owner": {
                "tenant_owner",
                "tenant_admin",
                "organizer",
                "manager",
                "gate_supervisor",
                "gate_scanner",
            },
            "tenant_admin": {
                "tenant_admin",
                "organizer",
                "manager",
                "gate_supervisor",
                "gate_scanner",
            },
        }
        if role not in delegate_roles.get(actor_member.role, set()):
            raise Forbidden("Cannot delegate this role")
        if role in {"organizer", "manager"} and event_id is None:
            raise ValueError("An event assignment is required")
        if role in {"gate_supervisor", "gate_scanner"} and (event_id is None or gate_id is None):
            raise ValueError("An event and gate assignment are required")
        invitation = new_token()
        with Session(self.engine) as db, db.begin():
            self._tenant(db, hostname)
            db.add(
                StaffInvitation(
                    tenant_id=tenant,
                    email=email.strip(),
                    role=role,
                    event_id=event_id,
                    gate_id=gate_id,
                    token_digest=token_digest(invitation),
                    invited_by=actor.id,
                    expires_at=utcnow() + timedelta(hours=48),
                )
            )
            self._audit(db, "invitation.issued", actor.id, tenant, {"role": role})
        self.email.send_link(
            email.strip(),
            "Your staff invitation",
            f"{base_url}/invite#token={quote(invitation)}",
        )

    def accept_invitation(self, hostname: str, token: str, password: str) -> tuple[str, str]:
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            invite = db.scalar(
                select(StaffInvitation)
                .where(StaffInvitation.token_digest == token_digest(token))
                .with_for_update()
            )
            if (
                invite is None
                or invite.tenant_id != tenant
                or invite.accepted_at
                or invite.revoked_at
                or invite.expires_at <= utcnow()
            ):
                raise AuthDenied("Invitation expired")
            user = db.scalar(select(User).where(User.email == invite.email))
            if user is None:
                self.corpus.require_acceptable(password)
                hashed = hash_password(password)
                user = User(email=invite.email, display_name=invite.email, status="active")
                db.add(user)
                db.flush()
                db.add(PasswordCredential(user_id=user.id, password_hash=hashed))
            else:
                credential = db.get(PasswordCredential, user.id)
                if user.status != "active" or not verify_password(
                    credential.password_hash if credential else None, password
                ):
                    raise AuthDenied("Invitation could not be accepted")
            if db.get(TenantMembership, (tenant, user.id)) is not None:
                raise AuthDenied("Membership already exists")
            mandatory = requires_mfa(invite.role)
            membership = TenantMembership(
                tenant_id=tenant,
                user_id=user.id,
                role=invite.role,
                status="pending_mfa" if mandatory else "active",
                invited_at=invite.created_at,
                accepted_at=None if mandatory else utcnow(),
            )
            db.add(membership)
            # EventAssignment has a composite FK to this row. The ORM has no
            # mapped relationship that orders these independent pending inserts.
            db.flush()
            if invite.event_id is not None:
                db.add(
                    EventAssignment(
                        tenant_id=tenant,
                        event_id=invite.event_id,
                        gate_id=invite.gate_id,
                        user_id=user.id,
                        valid_from=utcnow(),
                    )
                )
            invite.accepted_at = utcnow()
            self._audit(db, "invitation.accepted", user.id, tenant)
            if mandatory:
                raw = new_token()
                totp = db.get(TotpCredential, user.id)
                db.add(
                    AuthChallenge(
                        user_id=user.id,
                        tenant_id=tenant,
                        token_digest=token_digest(raw),
                        purpose="mfa" if totp and totp.confirmed_at else "enroll",
                        expires_at=utcnow() + timedelta(minutes=5),
                    )
                )
                return ("mfa" if totp and totp.confirmed_at else "enroll"), raw
            return "session", self._session(db, user.id, tenant, invite.role, False)

    def request_reset(self, hostname: str, email: str, ip: str) -> None:
        if isinstance(self.email, DisabledEmailDelivery):
            raise DeliveryUnavailable("Transactional email delivery is not configured")
        base_url = self._base_url(hostname)
        with Session(self.engine) as limiter, limiter.begin():
            tenant = self._tenant(limiter, hostname)
            self._limit(limiter, f"reset:account:{tenant}:{email.casefold()}", utcnow())
            self._limit(limiter, f"reset:ip:{tenant}:{ip}", utcnow(), 20)
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            user = db.scalar(select(User).where(User.email == email.strip()))
            if user is None or user.status != "active":
                return
            member = db.get(TenantMembership, (tenant, user.id))
            if member is None or member.status != "active":
                return
            raw = new_token()
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_digest=token_digest(raw),
                    expires_at=utcnow() + timedelta(minutes=30),
                )
            )
            self._audit(db, "password_reset.requested", user.id, tenant)
        self.email.send_link(
            email.strip(), "Reset your password", f"{base_url}/reset#token={quote(raw)}"
        )

    def complete_reset(self, hostname: str, token: str, password: str) -> None:
        self.corpus.require_acceptable(password)
        hashed = hash_password(password)
        with Session(self.engine) as db, db.begin():
            tenant = self._tenant(db, hostname)
            row = db.scalar(
                select(PasswordResetToken)
                .where(PasswordResetToken.token_digest == token_digest(token))
                .with_for_update()
            )
            if row is None or row.consumed_at is not None or row.expires_at <= utcnow():
                raise AuthDenied("Reset link expired")
            self._member(db, tenant, row.user_id)
            credential = db.get(PasswordCredential, row.user_id)
            if credential is None:
                raise AuthDenied("Reset link expired")
            credential.password_hash, credential.changed_at = hashed, utcnow()
            row.consumed_at = utcnow()
            db.execute(
                update(AuthSession)
                .where(
                    AuthSession.user_id == row.user_id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(revoked_at=utcnow())
            )
            self._audit(db, "password_reset.completed", row.user_id, tenant)

    def _base_url(self, hostname: str) -> str:
        host = normalize_hostname(hostname)
        if self.settings.app_env.value in {"local", "test"}:
            return f"http://{host}:5173"
        return f"https://{host}"
