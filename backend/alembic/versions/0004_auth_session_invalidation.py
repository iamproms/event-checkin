"""Revoke staff sessions when identity or tenant privileges change.

Revision ID: 0004_auth_session_invalidation
Revises: 0003_staff_identity
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_auth_session_invalidation"
down_revision: str | None = "0003_staff_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Membership writes belong to the identity service, never the tenant-data
    # runtime connection. This closes the M1-02 broad DML grant for this table.
    op.execute("REVOKE INSERT, UPDATE, DELETE ON tenant_memberships FROM eventcheckin_runtime")
    # The migration owner creates these narrowly scoped functions. Membership
    # writers cannot update the global session table directly; the trigger can.
    op.execute("""CREATE FUNCTION revoke_sessions_on_user_status_change()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
      SET search_path = pg_catalog AS $$
      BEGIN
        IF OLD.status IS DISTINCT FROM NEW.status THEN
          UPDATE public.auth_sessions SET revoked_at = clock_timestamp()
          WHERE user_id = NEW.id AND revoked_at IS NULL;
          UPDATE public.auth_challenges SET consumed_at = clock_timestamp()
          WHERE user_id = NEW.id AND consumed_at IS NULL;
          UPDATE public.password_reset_tokens SET consumed_at = clock_timestamp()
          WHERE user_id = NEW.id AND consumed_at IS NULL;
          INSERT INTO public.security_audit_events (actor_user_id, action, metadata)
          VALUES (NULL, 'user.status_changed',
            jsonb_build_object('target_user_id', NEW.id::text,
              'old_status', OLD.status, 'new_status', NEW.status,
              'database_login', session_user));
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION revoke_sessions_on_user_status_change() FROM PUBLIC")
    op.execute("""CREATE TRIGGER revoke_sessions_on_user_status_change
      AFTER UPDATE OF status ON users FOR EACH ROW
      WHEN (OLD.status IS DISTINCT FROM NEW.status)
      EXECUTE FUNCTION revoke_sessions_on_user_status_change()""")
    op.execute("""CREATE FUNCTION revoke_sessions_on_membership_change()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
      SET search_path = pg_catalog AS $$
      BEGIN
        IF OLD.status IS DISTINCT FROM NEW.status OR OLD.role IS DISTINCT FROM NEW.role THEN
          UPDATE public.auth_sessions SET revoked_at = clock_timestamp()
          WHERE tenant_id = NEW.tenant_id AND user_id = NEW.user_id
            AND revoked_at IS NULL;
          UPDATE public.auth_challenges SET consumed_at = clock_timestamp()
          WHERE tenant_id = NEW.tenant_id AND user_id = NEW.user_id
            AND consumed_at IS NULL;
          INSERT INTO public.security_audit_events
            (actor_user_id, tenant_id, action, metadata)
          VALUES (NULL, NEW.tenant_id, 'membership.changed',
            jsonb_build_object('target_user_id', NEW.user_id::text,
              'old_status', OLD.status, 'new_status', NEW.status,
              'old_role', OLD.role, 'new_role', NEW.role,
              'database_login', session_user));
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION revoke_sessions_on_membership_change() FROM PUBLIC")
    op.execute("""CREATE TRIGGER revoke_sessions_on_membership_change
      AFTER UPDATE OF status, role ON tenant_memberships FOR EACH ROW
      WHEN (OLD.status IS DISTINCT FROM NEW.status OR OLD.role IS DISTINCT FROM NEW.role)
      EXECUTE FUNCTION revoke_sessions_on_membership_change()""")


def downgrade() -> None:
    op.execute("DROP TRIGGER revoke_sessions_on_membership_change ON tenant_memberships")
    op.execute("DROP FUNCTION revoke_sessions_on_membership_change()")
    op.execute("DROP TRIGGER revoke_sessions_on_user_status_change ON users")
    op.execute("DROP FUNCTION revoke_sessions_on_user_status_change()")
    op.execute("GRANT INSERT, UPDATE, DELETE ON tenant_memberships TO eventcheckin_runtime")
