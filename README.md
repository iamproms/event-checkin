# Event Check-in Platform

## Event-first shared-host release candidate

The event-first branch adds migration `0012_shared_event_release`. The platform host has one staff sign-in and an organization form that requires only an organization name and organizer email. After account setup and MFA, organizers use the same host for their tenant-scoped workspace. Newly created events default to import-only mode; CSV files may contain only an email column. Import, QR issuance, and ticket sending are separate actions. The established custom-domain and public-registration paths remain available. Migration `0013_privacy_notice_workflow` adds platform-admin notice drafting, approval, and activation; see [privacy import workflow](docs/PRIVACY_IMPORT_WORKFLOW.md).

For a local rehearsal, back up the database and apply the new migration, then run the local HTTPS services. On the existing development workstation, the private, Git-ignored helper `bash .env.local-event-smoke` performs those steps; fresh checkouts should follow [Local startup](#local-startup) and the [HTTPS host runbook](docs/M2-01_PROVISIONING_RUNBOOK.md). Open the platform hostname at `/`, create the organization in `/platform-console.html#organizations`, inspect the local Mailpit inbox, and follow the invitation. Remote delivery uses the Brevo adapter only when its restricted API key, verified sender and authenticated webhook are configured. See the [production deployment plan](docs/PRODUCTION_DEPLOYMENT_PLAN.md) and [staging runbook](docs/EVENT_STAGING_DEPLOYMENT_RUNBOOK.md) for the remaining release gates.

M2-03 event configuration: see [event API contracts](docs/M2-03_EVENT_API_CONTRACTS.md) and [local runbook](docs/M2-03_EVENT_RUNBOOK.md). The event interface is at `/events.html` on an authorized tenant host. The combined provider-independent M2-04/M3-01/M3-02 foundation adds `/branding.html` and `/register.html?event={slug}`; see the [operations runbook](docs/M2-04_M3-01_M3-02_RUNBOOK.md).

M1-01 foundation through M1-05 shared UI primitives and M2-01 tenant provisioning are merged. The API is FastAPI; the web workspace is React, TypeScript and Vite. Approved decisions D-01–D-13, [G-02](docs/DECISIONS/G-02_STAFF_IDENTITY.md), [G-07](docs/DECISIONS/G-07_VISUAL_FOUNDATION.md), and the [M1-04 decision record](docs/DECISIONS/M1-04_JOBS_FILES.md) govern this work.

M1-03 uses versioned `/api/v1/auth` routes. M1-04 adds no public job or file routes. M2-03 adds event configuration. M2-04/M3-01/M3-02 add reviewed branding, public registration and ticket-delivery foundations. The current unmerged event-first work adds bulk import, atomic online redemption, live attendance and basic export. M2-02 billing remains deferred.

The immediate operational release path for the 1 November 2026 event is tracked
in the [event staging deployment and rehearsal runbook](docs/EVENT_STAGING_DEPLOYMENT_RUNBOOK.md).
It includes the Vercel frontend and authenticated Render API origin, environment inventory,
external approval blockers, 5,000-person synthetic rehearsal, five-gate race
criteria, backup/restore and rollback rules. The document is deployment
preparation, not evidence that a staging or production deployment has occurred.

## Product experience

The frontend is organized into three coherent experiences while preserving the existing host and authentication boundaries:

- Platform Console: `/platform-console.html` with overview, simple shared-host organization creation, domains, subscriptions, operations and settings. The older domain-based provisioning flow remains at `/platform.html` for custom-domain use.
- Organizer Workspace: `/workspace.html` with live dashboard, events, participants and import, tickets, check-in, gate staff, reports, branding and settings. Communications is deferred.
- Gate operations: `/gate.html`, with scoped assignment and online server redemption. Admission is shown only after an accepted server response. Camera QR decoding uses the native browser detector where available and a bundled decoder otherwise; the manual credential field remains available.
- Public attendee registration: `/register.html?event={slug}`, using the published tenant brand and hostname-derived public API.

Every future-facing surface is labeled `Demo data`, `Training demo`, or `Not connected`. Existing live event, branding and domain workflows remain available at `/events.html`, `/branding.html`, and `/domains.html`. See the [frontend architecture, route map and capability matrix](docs/FRONTEND_PRODUCT_ARCHITECTURE.md).

## Local startup

Prerequisites: Docker with Compose, Python 3.12 or 3.13, Node 22, and npm.

### Existing Fedora HTTPS workstation

The workstation's `.env` and `.env.compose.override.yaml` are private local
configuration. After changing the API or Vite Docker source, rebuild only those
images once. Routine restarts reuse them and preserve database volumes:

```sh
docker compose -f compose.yaml -f .env.compose.override.yaml --env-file .env build api web
bash ops/local-browser-start.sh
bash ops/local-browser-check.sh --login-probe
```

`local-browser-start.sh` waits for container health and checks `/health`,
`/ready`, platform CSRF, and the current organization screen through local
HTTPS. It reports occupied ports and failed services. If the earlier host-mode
helpers own port 8443, run `bash .env.local-stop` once before starting Compose.
The optional login probe
uses one synthetic invalid account to verify the CSRF cookie and HTTPS Origin;
it cannot verify an administrator's password or MFA. Open
`https://platform.local.example.test:8443/` for the shared sign-in, then use
`/platform-console.html` after authentication. The Git-ignored
`.env.local-event-smoke` additionally backs up and checks migrations; it is not
needed for an ordinary browser restart.

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
export REDIS_URL='redis://localhost:6380/0'
export TICKET_KEYRING_JSON='{"1":"REPLACE_WITH_BASE64_32_BYTES"}'
export TICKET_ACTIVE_KEY_VERSION=1
export TICKET_ISSUANCE_ENABLED=true
export REGISTRATION_RATE_HMAC_KEY="$(openssl rand -hex 32)"
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
npm run test:tokens
npx playwright install chromium
npm run test:ui
```

The isolated M1-05 component examples are at `http://127.0.0.1:5173/ui-lab.html` in Vite development mode. They are not application screens or a production entry. See the [component contracts](frontend/src/ui/README.md) and [state vocabulary v1](docs/DECISIONS/M0-02_STATE_VOCABULARY_V1.md). M2-01 adds `/platform.html` and `/domains.html`; their authenticated browser flow requires a local HTTPS hostname/edge because session cookies remain Secure. The Vite HTTP development server supports component and mocked-browser checks, not a real local sign-in on a custom `.test` hostname. See the [M2-01 runbook](docs/M2-01_PROVISIONING_RUNBOOK.md).

`/health` is a process liveness check. `/ready` checks database connectivity and returns HTTP 503 when it fails. Its `worker` field remains `not_configured`: M1-04 worker/queue health is inspected through the restricted [jobs runbook](docs/M1-04_JOBS_STORAGE_RUNBOOK.md), and Redis availability does not gate API readiness or future authoritative scan writes. No raw database exception or URL is returned by either endpoint.

## Environment and migration policy

`APP_ENV` must be `local`, `test`, `staging`, or `production`; `DATABASE_URL` is required. Staging and production reject loopback database URLs and require an explicit PostgreSQL TLS mode. Production requires `sslmode=verify-full` for runtime, identity, job, and operator connections, plus a trusted database CA. The deployment platform must inject secrets at runtime; example files contain placeholders only. Do not commit real `.env` files. Migrations `0002`–`0013` cover tenant isolation, identity, reliable jobs/storage, domains, event configuration, branding, registration evidence, ticket delivery, import and check-in evidence, shared-host event release, and the privacy notice approval workflow. `TICKET_KEYRING_JSON` and `REGISTRATION_RATE_HMAC_KEY` are secrets; generate independent remote values and never use the local fixture. See [schema notes](docs/M1-02_SCHEMA_NOTES.md), [identity contracts](docs/M1-03_AUTH_CONTRACTS.md), [jobs runbook](docs/M1-04_JOBS_STORAGE_RUNBOOK.md), [M2-01 runbook](docs/M2-01_PROVISIONING_RUNBOOK.md), and the [combined registration/ticket runbook](docs/M2-04_M3-01_M3-02_RUNBOOK.md).

Run migrations as a **single release step before routing traffic to new code**. Back up first, review generated SQL and destructive operations, and rehearse on staging. Prefer a forward fix after a migration reaches production; downgrade only when explicitly reviewed as safe for existing data. The baseline and M1-02 migration can be upgraded and downgraded on an empty database; do not downgrade a populated database without a reviewed data plan.

## Open production completion gates

The providers are fixed for this event (GitHub, Vercel, Render, Supabase and Brevo), but regions, plans, domains, credentials, privacy/DPA approval, backup retention and an exercised restore remain external gates. No staging or production deployment has occurred. CI must still run the synchronous FastAPI contract suite outside the local sandbox, and dependency, secret and container scanning plus immutable image evidence remain required before approval. Follow the [release integration report](docs/RELEASE_INTEGRATION_REPORT.md) for the current evidence and risks.

