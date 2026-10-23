# Event Check-in Platform

M1-01 foundation, M1-02 tenant schema, M1-03 staff authentication, and M1-04 reliable-job/private-file primitives are in this branch. The API is FastAPI; the web workspace is React, TypeScript and Vite. Approved decisions D-01–D-13, [G-02](docs/DECISIONS/G-02_STAFF_IDENTITY.md), and the [M1-04 decision record](docs/DECISIONS/M1-04_JOBS_FILES.md) govern this work.

M1-03 uses versioned `/api/v1/auth` routes. M1-04 adds no public job or file routes. Event, QR, billing, and scanner features remain outside this milestone.

## Local startup

Prerequisites: Docker with Compose, Python 3.12 or 3.13, Node 22, and npm.

### Containers

```sh
export AUTH_ENCRYPTION_KEY="$(openssl rand -base64 32)"
docker compose up --build -d db redis object-storage object-storage-init
docker compose run --rm role-setup
docker compose run --rm migrate
docker compose up --build -d api web mailpit worker dispatcher storage-maintenance
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

Generate the encryption key once, store it outside Git, and reuse it across restarts. Changing it without re-encrypting stored TOTP secrets makes enrolled authenticators unusable.

The API is at `http://127.0.0.1:8000`; the staff authentication workspace is at `http://127.0.0.1:5173`. Mailpit’s local inbox is at `http://127.0.0.1:8025`. PostgreSQL, Redis, and object storage bind only to loopback with **local-only** credentials in `compose.yaml`. Stop with `docker compose down`; add `-v` only when intentionally deleting local data.

Local S3 tests use the pinned `rustfs/rustfs:1.0.1` server. Bucket setup runs through Boto3 in the backend image; no separate storage-client image is needed. On an existing shared Compose project, follow the [storage-only startup steps](docs/M1-04_JOBS_STORAGE_RUNBOOK.md) to preserve running M1-03 services and volumes.

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

`/health` is a process liveness check. `/ready` checks database connectivity and returns HTTP 503 when it fails. Its `worker` field remains `not_configured`: M1-04 worker/queue health is inspected through the restricted [jobs runbook](docs/M1-04_JOBS_STORAGE_RUNBOOK.md), and Redis availability does not gate API readiness or future authoritative scan writes. No raw database exception or URL is returned by either endpoint.

## Environment and migration policy

`APP_ENV` must be `local`, `test`, `staging`, or `production`; `DATABASE_URL` is required. Staging and production reject loopback database URLs and require an explicit PostgreSQL TLS mode. Production requires `sslmode=verify-full` for runtime, identity, job, and operator connections, plus a trusted database CA. The deployment platform must inject secrets at runtime; example files contain placeholders only. Do not commit real `.env` files. Migrations `0002_tenant_foundation`, `0003_staff_identity`, `0004_auth_session_invalidation`, and `0005_reliable_jobs_storage` add tenant isolation, staff identity, session invalidation, and reliable-job/private-object primitives respectively. See [schema notes](docs/M1-02_SCHEMA_NOTES.md), [identity contracts](docs/M1-03_AUTH_CONTRACTS.md), and [jobs runbook](docs/M1-04_JOBS_STORAGE_RUNBOOK.md).

Run migrations as a **single release step before routing traffic to new code**. Back up first, review generated SQL and destructive operations, and rehearse on staging. Prefer a forward fix after a migration reaches production; downgrade only when explicitly reviewed as safe for existing data. The baseline and M1-02 migration can be upgraded and downgraded on an empty database; do not downgrade a populated database without a reviewed data plan.

## Open M1-01 completion gates

The M0-02 launch domain/API contracts and G-06 provider, region and privacy/vendor decisions remain open. No infrastructure as code, managed secrets integration, staging deployment, or deployment/rollback rehearsal can be finalized without a target environment. M1-04 adds local Redis and private S3-compatible storage, without selecting production providers. CI does not yet perform dependency, secret or container scanning. A backend lockfile and immutable container image references should be added before claiming repeatable releases. These items are required before M1-01 is marked complete.

