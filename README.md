# Event Check-in Platform

M1-01 foundation, M1-02 tenant schema, and M1-03 staff-authentication work on this feature branch. The API is FastAPI; the web workspace is React, TypeScript and Vite. Approved decisions D-01–D-13 and [G-02](docs/DECISIONS/G-02_STAFF_IDENTITY.md) govern this work. See [M1-03 identity contracts](docs/M1-03_AUTH_CONTRACTS.md).

M1-03 uses versioned `/api/v1/auth` routes. Event, QR, billing, scanner, and the remaining M0-02 contracts stay outside this milestone.

## Local startup

Prerequisites: Docker with Compose, Python 3.12 or 3.13, Node 22, and npm.

### Containers

```sh
export AUTH_ENCRYPTION_KEY="$(openssl rand -base64 32)"
docker compose up --build -d
docker compose run --rm migrate
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

Generate the encryption key once, store it outside Git, and reuse it across restarts. Changing it without re-encrypting stored TOTP secrets makes enrolled authenticators unusable.

The API is at `http://127.0.0.1:8000`; the staff authentication workspace is at `http://127.0.0.1:5173`. Mailpit’s local inbox is at `http://127.0.0.1:8025`. PostgreSQL is bound to `127.0.0.1:5433` with **local-only** credentials in `compose.yaml`. Stop with `docker compose down`; add `-v` only when intentionally deleting local data.

### Host development

```sh
docker compose up -d db role-setup
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[dev]'
cd backend
source .venv/bin/activate
export APP_ENV=local
export DATABASE_URL='postgresql+psycopg://eventcheckin:local_dev_only@localhost:5433/eventcheckin'
alembic upgrade head
export DATABASE_URL='postgresql+psycopg://eventcheckin_app:local_app_only@localhost:5433/eventcheckin'
export IDENTITY_DATABASE_URL='postgresql+psycopg://eventcheckin_identity_app:local_identity_only@localhost:5433/eventcheckin'
export AUTH_ENCRYPTION_KEY="$(openssl rand -base64 32)"
export EMAIL_SMTP_HOST=localhost
export EMAIL_SMTP_PORT=1025
export EMAIL_FROM=staff@local.example.test
uvicorn app.main:app --reload --port 8000
```

In another terminal: `cd frontend && npm install && npm run dev`. For local host tools, the `.env.local.example` file lists the required values. A verified tenant hostname and initial owner are still needed to use the staff flow. To enable new credentials, supply an approved, versioned compromised-password corpus path and its whole-file SHA-256; the API fails closed without it. Do not use local credentials in any remote environment. The service reads process environment variables; it does not automatically load `.env` files.

## Checks

```sh
cd backend
ruff check .
mypy app
pytest -q
alembic upgrade head
alembic downgrade 0002_tenant_foundation # isolated empty test database only
alembic upgrade head
cd ../frontend
npm run lint
npm run typecheck
npm run build
```

`/health` is a process liveness check. `/ready` checks database connectivity and returns HTTP 503 when it fails. Its `worker` field is `not_configured` until M1-04 establishes a real worker/broker contract; it is intentionally not reported as healthy or used to gate API readiness. No raw database exception or URL is returned by either endpoint.

## Environment and migration policy

`APP_ENV` must be `local`, `test`, `staging`, or `production`; `DATABASE_URL` is required. Staging and production reject loopback database URLs and require an explicit PostgreSQL TLS mode. Production requires `sslmode=verify-full` for both runtime and identity connections and a trusted database CA. The deployment platform must inject secrets at runtime; example files contain placeholders only. Do not commit real `.env` files. Migrations `0002_tenant_foundation`, `0003_staff_identity`, and `0004_auth_session_invalidation` add tenant isolation, staff identity, and session invalidation respectively. See [schema notes](docs/M1-02_SCHEMA_NOTES.md) and [identity contracts](docs/M1-03_AUTH_CONTRACTS.md).

Run migrations as a **single release step before routing traffic to new code**. Back up first, review generated SQL and destructive operations, and rehearse on staging. Prefer a forward fix after a migration reaches production; downgrade only when explicitly reviewed as safe for existing data. The baseline and M1-02 migration can be upgraded and downgraded on an empty database; do not downgrade a populated database without a reviewed data plan.

## Open M1-01 completion gates

The M0-02 launch domain/API contracts and G-06 provider, region and privacy/vendor decisions remain open. No infrastructure as code, managed secrets integration, staging deployment, or deployment/rollback rehearsal can be finalized without a target environment. Redis and private S3-compatible object storage are approved architectural components but no tasks or artifacts use them until M1-04, so their runtime connections are deferred. CI does not yet perform dependency, secret or container scanning. A lockfile and immutable container image references should be added before claiming repeatable releases. These items are required before M1-01 is marked complete.

