# M1-02 tenant schema and test notes

**Status:** Feature branch for review. M1-01 staging/production hardening remains open. This schema does not approve open product policies.

## Contract boundary

D-01, D-05, D-06/D-11, and D-10 support the tenant/event/registration structure, one event check-in session, event-end retention anchor, and independent per-event email/phone uniqueness. The database design supports domain records, memberships, tickets, and retained event summary. M0-02 has not frozen event/registration lifecycle states, staff authentication, scan outcomes, job states, billing terms, or aggregate privacy thresholds. Those fields are kept as text where their state machine is open, or their tables are deferred.

`0002_tenant_foundation` creates `tenants`, `users`, `tenant_domains`, `tenant_branding`, `tenant_memberships`, `events`, `gates`, `registrations`, `tickets`, and `event_summary`. No authentication, registration, ticket, scanning, or reporting command is implemented. `tickets` is an integrity shell for future issuance; no QR secret is created. `event_summary` has counts only. Detailed `event_aggregates`, check-ins, scan attempts, sessions, assignments, jobs, campaigns, billing, and audit tables await their owning feature/policy contracts. This is a staged subset of DATABASE_DESIGN.md, not a replacement for its full launch model.

Each tenant table has forced RLS and a tenant-leading key/index. Event children use composite `(tenant_id,event_id)` foreign keys; tickets additionally bind registration ID to the same tenant and event. Case-insensitive `citext` email keeps plus tags distinct, rejects leading/trailing whitespace, and has a separate partial unique index from canonical E.164 phone. Phone format is checked in PostgreSQL; parsing to E.164 before insertion belongs to the registration command. Deleted registrations still carry PII until the later deletion workflow; that workflow must scrub or hard-delete them, not merely set `deleted_at`. `pii_purge_due_at` is required and anchored by D-11, while enforcement of recalculation when `ends_at` changes belongs to the event command. No retention job exists yet.

## Trust boundary and roles

`eventcheckin` owns and migrates the local database. `eventcheckin_app` is a separate local login that inherits only the `eventcheckin_runtime` **NOLOGIN/NOBYPASSRLS** group. It cannot read platform `tenants` or `users`, own tenant tables, or bypass RLS. It has read-only access to tenant-scoped domain rows; domain verification and TLS state changes require the future privileged platform path. A dedicated **NOLOGIN/NOBYPASSRLS** `eventcheckin_domain_resolver` owns only the fixed SQL security-definer lookup and has SELECT on `tenant_domains` through a role-specific read policy; it is never granted to the runtime login. The function returns a tenant ID only for a verified domain with active TLS. Its search path is fixed, PUBLIC execute is revoked, and its input is bound. Production role provisioning and secrets must use a privileged migration/bootstrap process selected during M1-01 hardening; the committed passwords are local-only placeholders.

`tenant_session_for_domain()` accepts a server-trusted hostname, normalizes it, calls the resolver, and applies `set_config(..., true)` inside the same SQLAlchemy transaction. Missing or unknown domains fail before any tenant query. A client tenant ID or arbitrary forwarded host is never accepted as authority. M1-03 must add membership verification for authenticated paths and edge host validation; this utility alone is only the public domain-derived boundary. The runtime DB credential must not be exposed to clients or arbitrary SQL execution, because PostgreSQL custom settings are writable by the connected role.

The migration creates the `citext` extension and two NOLOGIN roles when absent. It therefore needs migration privileges to create extensions/roles and to transfer ownership of the resolver function. It never gives the application login table ownership or BYPASSRLS. The local `role-setup` Compose service idempotently provisions only the development login and group membership, including on existing volumes. It does not reset data.

## Validation

For a local PostgreSQL instance with an owner login able to create ephemeral databases and roles:

```sh
export TEST_MIGRATION_DATABASE_URL='postgresql+psycopg://eventcheckin:local_dev_only@localhost:5433/postgres'
cd backend
pytest -q tests/test_tenant_postgres.py
ruff check .
mypy app
```

The integration fixture creates two uniquely named temporary databases. One migrates through `0001_foundation` then `0002_tenant_foundation`; the other migrates fresh to head. It creates a temporary non-owner runtime login, seeds fixtures, tests RLS, constraints and concurrency, then drops **only those fixture databases and login**. It does not touch the existing `eventcheckin` database or volume. When the URL is absent, local integration tests skip; CI must provide it and fails if missing. The CI PostgreSQL service uses an isolated local credential.

To upgrade the existing local database without resetting its volume:

```sh
docker compose up -d db role-setup
docker compose run --rm migrate
docker compose exec db psql -U eventcheckin -d eventcheckin -c 'SELECT version_num FROM alembic_version'
```

Do not run `alembic downgrade 0001_foundation` on populated event data. A forward migration is the preferred recovery path after deployment; a downgrade requires a reviewed backup and data-loss decision.
