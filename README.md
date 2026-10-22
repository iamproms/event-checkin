# Event Check-in Platform

M1-01 engineering foundation. The API is FastAPI; the web workspace is React, TypeScript and Vite. No product features or application screens are implemented yet. Approved product decisions D-01–D-13 remain in [the PRD review](docs/PRD_REVIEW.md).

The minimum M0-02 contract used here is limited to `/api/v1` for future feature routes, separate health/readiness behavior, four named environments, and Alembic revision ordering. Event states, API errors, metrics, identity, QR, and provider contracts remain for M0-02 review. This foundation does not pre-approve them.

## Local startup

Prerequisites: Docker with Compose, Python 3.12 or 3.13, Node 22, and npm.

### Containers

```sh
docker compose up --build -d
docker compose exec api alembic upgrade head
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

The API is at `http://127.0.0.1:8000`; the blank web workspace is at `http://127.0.0.1:5173`. PostgreSQL is bound to `127.0.0.1:5433` with **local-only** credentials in `compose.yaml`. Stop with `docker compose down`; add `-v` only when intentionally deleting local data.

### Host development

```sh
docker compose up -d db
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[dev]'
cd backend
source .venv/bin/activate
export APP_ENV=local
export DATABASE_URL='postgresql+psycopg://eventcheckin:local_dev_only@localhost:5433/eventcheckin'
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In another terminal: `cd frontend && npm install && npm run dev`. For local host tools, the `.env.local.example` file lists the required values. Do not use its local credentials in any remote environment. The service reads process environment variables; it does not automatically load `.env` files.

## Checks

```sh
cd backend
ruff check .
mypy app
pytest -q
alembic upgrade head
alembic downgrade base
alembic upgrade head
cd ../frontend
npm run lint
npm run typecheck
npm run build
```

`/health` is a process liveness check. `/ready` checks database connectivity and returns HTTP 503 when it fails. Its `worker` field is `not_configured` until M1-04 establishes a real worker/broker contract; it is intentionally not reported as healthy or used to gate API readiness. No raw database exception or URL is returned by either endpoint.

## Environment and migration policy

`APP_ENV` must be `local`, `test`, `staging`, or `production`; `DATABASE_URL` is required. Staging and production reject loopback database URLs and require an explicit PostgreSQL TLS mode. The deployment platform must inject secrets at runtime; example files contain placeholders only. Do not commit real `.env` files. The current migration `0001_foundation` creates only Alembic's version record, leaving tenant schema for M1-02.

Run migrations as a **single release step before routing traffic to new code**. Back up first, review generated SQL and destructive operations, and rehearse on staging. Prefer a forward fix after a migration reaches production; downgrade only when explicitly reviewed as safe for existing data. The blank baseline can be upgraded and downgraded; future migrations need their own data rollback notes.

## Open M1-01 completion gates

The M0-02 launch domain/API contracts and G-06 provider, region and privacy/vendor decisions remain open. No infrastructure as code, managed secrets integration, staging deployment, or deployment/rollback rehearsal can be finalized without a target environment. Redis and private S3-compatible object storage are approved architectural components but no tasks or artifacts use them until M1-04, so their runtime connections are deferred. CI does not yet perform dependency, secret or container scanning. A lockfile and immutable container image references should be added before claiming repeatable releases. These items are required before M1-01 is marked complete.

