"""Transaction-scoped tenant context for public domain-derived operations.

Authentication and membership verification are intentionally deferred to M1-03.
Do not pass an untrusted client tenant ID to a database transaction.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


class TenantResolutionError(ValueError):
    """A host did not resolve to one active verified tenant domain."""


def normalize_hostname(hostname: str) -> str:
    candidate = hostname.strip().rstrip(".").lower()
    if not candidate or ":" in candidate or "/" in candidate or len(candidate) > 253:
        raise TenantResolutionError("Unrecognized tenant domain")
    try:
        ascii_name = candidate.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise TenantResolutionError("Unrecognized tenant domain") from exc
    if any(not label or len(label) > 63 for label in ascii_name.split(".")):
        raise TenantResolutionError("Unrecognized tenant domain")
    return ascii_name


@contextmanager
def tenant_session_for_domain(engine: Engine, trusted_hostname: str) -> Iterator[Session]:
    """Resolve an edge-validated host in the database, then bind its tenant to this transaction.

    The caller must obtain `trusted_hostname` from the validated request authority,
    never from a user-supplied tenant ID or arbitrary forwarded header. The
    security-definer resolver only returns verified domains with active TLS.
    """
    hostname = normalize_hostname(trusted_hostname)
    with Session(engine) as session, session.begin():
        tenant_id = session.execute(
            text("SELECT resolve_active_tenant_domain(:hostname)"), {"hostname": hostname}
        ).scalar_one()
        if not isinstance(tenant_id, UUID):
            raise TenantResolutionError("Unrecognized tenant domain")
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        yield session
