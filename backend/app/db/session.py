"""Transaction-scoped tenant context for public domain-derived operations.

Do not pass an untrusted client tenant ID to a database transaction.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import idna
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


class TenantResolutionError(ValueError):
    """A host did not resolve to one active verified tenant domain."""


def normalize_hostname(hostname: str) -> str:
    # One canonical IDNA2008/UTS-46 A-label form is used for claims and lookup.
    # Strict request authority parsing is performed before this function.
    candidate = hostname.strip().removesuffix(".")
    if (
        not candidate
        or ":" in candidate
        or "/" in candidate
        or "@" in candidate
        or "\\" in candidate
    ):
        raise TenantResolutionError("Unrecognized tenant domain")
    try:
        ascii_name = idna.encode(candidate, uts46=True, std3_rules=True).decode("ascii").lower()
        if (
            idna.encode(idna.decode(ascii_name), uts46=True, std3_rules=True).decode("ascii")
            != ascii_name
        ):
            raise TenantResolutionError("Unrecognized tenant domain")
    except idna.IDNAError as exc:
        raise TenantResolutionError("Unrecognized tenant domain") from exc
    if len(ascii_name) > 253 or "." not in ascii_name:
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
        tenant_id: UUID | None = session.execute(
            text("SELECT resolve_active_tenant_domain(:hostname)"), {"hostname": hostname}
        ).scalar_one_or_none()
        if not isinstance(tenant_id, UUID):
            raise TenantResolutionError("Unrecognized tenant domain")
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        yield session


@contextmanager
def authorized_tenant_session(engine: Engine, authorized_tenant_id: UUID) -> Iterator[Session]:
    """Bind only a tenant ID returned by the server-side authorization service.

    The caller must first validate the session, current active membership and
    effective permission. The runtime role cannot bypass FORCE RLS.
    """
    with Session(engine) as session, session.begin():
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(authorized_tenant_id)},
        )
        yield session
