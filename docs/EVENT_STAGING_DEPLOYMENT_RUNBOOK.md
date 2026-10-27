# Event-critical staging deployment and rehearsal

**Status:** Prepared deployment shape; not deployed or production-approved.
**Event target:** 1 November 2026, configurable entry gates, 3,000–5,000 attendees.
**Security baseline:** Online, server-confirmed redemption; signed shared-host routing context;
separate database roles; secure host-only sessions; CSRF and MFA remain enabled.

This runbook is the shortest safe path from the current repository to an
event rehearsal. It deliberately does not select a data region, accept vendor
terms, approve a privacy notice, or claim that current local-only email/domain
adapters work remotely.

## Release blockers that require an owner outside the repository

The following inputs are required before a real-attendee staging exercise:

1. An approved deployment/data region and vendor/DPA decision (G-06).
2. An approved HTTPS platform hostname and Cloudflare/edge configuration. Individual organization domains are optional.
3. Render (or equivalent) credentials, paid service sizes, and origin domain.
4. Managed PostgreSQL with owner access to create the required `NOBYPASSRLS`
   login roles, plus an approved backup/PITR retention policy.
5. Managed Redis with TLS and private connectivity.
6. Private S3-compatible storage, region, lifecycle, credentials and recovery
   policy. The local RustFS container is not a remote deployment choice.
7. An approved, versioned compromised-password corpus mounted into every auth
   process, with its whole-file SHA-256.
8. An approved privacy notice, lawful basis and import-notice procedure for the
   actual attendee list. A bulk import does not record attendee acknowledgement;
   its evidence is the active notice and operator-attested basis.
9. A transactional email provider, verified sender/domain, delivery callback
   authentication and idempotency agreement. The current application enables
   SMTP ticket/auth transports only in `local` and `test`; setting SMTP values
   in staging does **not** enable delivery.
10. Event-day support owners, escalation contacts, venue primary/backup
    connectivity and one charged, camera-tested device per configured gate.

Continue synthetic local and isolated staging work while these are resolved.
Do not collect real participant data or tell attendees a ticket was sent until
the notice and delivery gates are complete.

## Prepared service topology

```text
Browser
  -> Cloudflare Worker (TLS, public Host, client-IP normalization,
                        secret origin authentication)
  -> combined Render web container
       Caddy :$PORT (static React + /api reverse proxy)
       Uvicorn 127.0.0.1:8000 (no proxy-header processing)
  -> managed PostgreSQL / Redis / private object storage

Separate restricted processes:
  Celery worker
  outbox dispatcher
  domain maintenance scheduler
  storage maintenance worker
```

The combined web image is [Dockerfile.web](../ops/deploy/Dockerfile.web). Caddy
is the API's only immediate ingress peer, so `INGRESS_PROXY_IPS=127.0.0.1` is
correct for this topology. That setting alone does **not** prove Cloudflare was
the caller. Every HTTP request must also carry the edge-only secret header;
Caddy rejects unmatched direct-origin requests and removes the private headers
before Uvicorn. The Worker deletes any client-supplied private headers, then
sets the client address and public Host from Cloudflare-controlled inputs. Remote
canonical origin is forced to HTTPS by the application, so
`X-Forwarded-Proto` is not an authority input.

The Render `onrender.com` hostname must be disabled after attaching the custom
origin domain. Put that origin outside the Worker route—for example, route
`*.events.staging.example.test` through the Worker while using
`origin.staging.example.test` for Render—to prevent a recursive Worker fetch.
Cloudflare SSL mode must be Full (strict). An authenticated
origin path is mandatory; a public origin protected only by an obscure URL is
not acceptable. The provided Worker/header design is a candidate pending G-06,
not a provider approval.

## Configuration inventory

Start from [.env.staging.example](../.env.staging.example). Store values in the
deployment secret manager, never a checked-in `.env` file.

| Consumer | Required restricted settings |
|---|---|
| Web/API | runtime, identity, platform DB URLs; auth key/corpus; host/suffix; Redis; storage; ticket keyring; rate HMAC; approved mail adapter |
| Celery worker | runtime and jobs DB URLs; Redis; storage where required; ticket keyring; mail adapter |
| Dispatcher | runtime and dispatcher DB URLs; Redis |
| Domain maintenance | runtime and domain-scheduler DB URLs; platform host/suffix |
| Storage maintenance | runtime and job-operator DB URLs; storage credentials |
| Release command only | migration-owner DB URL |
| One-time bootstrap only | bootstrap DB URL; remove after use |

Use independent random values for the authentication key, ticket keyring,
registration-rate HMAC and origin-auth secret. Preserve versioned keys across
deployments. Never rotate them merely to restart a service.

## Provision and deploy staging

1. Copy `ops/deploy/render.staging.yaml.example` to a private deployment branch
   or configure the equivalent services in the provider console. Replace the
   deliberately invalid `REQUIRES_G06_REGION` only after G-06 approval.
2. Create the PostgreSQL login roles outside Alembic, grant each membership in
   the corresponding NOLOGIN role, and verify every login has `NOBYPASSRLS`.
   Follow `ops/local_roles.sql` for role names, but do not reuse its passwords.
3. Populate the least-privilege environment groups referenced by the template:
   `event-checkin-web-staging`, `event-checkin-worker-staging`,
   `event-checkin-dispatcher-staging`, `event-checkin-domain-staging`, and
   `event-checkin-storage-staging`. Follow the consumer table above. Do not
   expose the migration-owner, bootstrap, operator, platform or identity
   credential to a process that does not need it.
4. Build locally before provider sync:

   ```sh
   docker build -f ops/deploy/Dockerfile.web -t event-checkin-web:staging-check .
   docker build -t event-checkin-backend:staging-check backend
   ```

5. Back up the staging database, then run migrations once with the migration
   owner from the exact release image:

   ```sh
   docker run --rm \
     -e APP_ENV=staging \
     -e DATABASE_URL="$MIGRATION_DATABASE_URL" \
     event-checkin-backend:staging-check \
     alembic upgrade head
   ```

   Provide secrets through the operator environment/secret manager. Do not put
   actual URLs into shell history. Confirm `alembic current` reports the single
   expected head before routing traffic.

6. Deploy web, worker, dispatcher and maintenance services at the same image
   revision. `GET /health` is liveness; `GET /ready` is API/database readiness.
   The current `worker: not_configured` field is not a worker health assertion.
7. Deploy the Worker using the example Wrangler configuration, bind
   `ORIGIN_AUTH_SECRET` using `wrangler secret put`, and set the same value on
   the web service. Never put it in `wrangler.toml`.
8. Attach the platform and tenant staging hostnames, enable Full (strict),
   disable the provider subdomain, and prove that every direct-origin HTTP path
   returns 404 while the approved hostname works. The Blueprint intentionally
   uses Render's default TCP health check because an HTTP health check cannot
   carry the origin-auth header; `/health` and `/ready` remain available through
   the authenticated edge.
9. Bootstrap the platform administrator interactively using the restricted
   bootstrap credential, then remove that credential from all runtime services.
10. Sign in on the platform hostname, create the organization with its name and
    organizer email, and confirm invitation transport acceptance. The shared
    host requires no per-organization DNS/TLS setup. If a custom domain is
    added later, its ownership, TLS and routing evidence remain mandatory.

Migration `0012_shared_event_release` adds import-only events, a limited
cross-tenant identity-context lookup, and idempotent shared onboarding. Review
its role grants before applying it to remote PostgreSQL. A platform session
does not provide tenant participant access.

The present remote domain provider is deliberately disabled. Real DNS/TLS/smoke
reconciliation requires an approved provider adapter; a manual database update
is not a substitute.

## Post-deploy verification

Run from an authorized operator workstation without printing secrets:

```sh
curl --fail --silent --show-error https://PLATFORM_HOST/health
curl --fail --silent --show-error https://PLATFORM_HOST/ready
curl --fail --silent --show-error https://PLATFORM_HOST/ >/dev/null
test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
  https://RENDER_ORIGIN_HOST/)" = 404
test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
  https://RENDER_ORIGIN_HOST/api/v1/auth/csrf)" = 404
test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
  https://RENDER_ORIGIN_HOST/ready)" = 404
```

In the provider and application logs, confirm:

- no raw cookies, CSRF values, invitation tokens, QR credentials or participant
  fields are logged;
- one dispatcher is leasing outbox rows and workers are draining jobs;
- job retry/dead counts, outbox age and database connections are stable;
- tenant routes on the platform host require a signed routing context plus a
  separate tenant-bound staff session; an unknown Host fails 421;
- a ticket is not reported delivered until the real provider contract confirms
  the appropriate state.

## 5,000-person and five-gate rehearsal

Generate the fixtures and follow [tests/load/README.md](../tests/load/README.md).
Use a capture/sink mail adapter and reconcile database rows rather than sending
thousands of messages. Minimum evidence:

- 5,000-row import preview/commit and row-error correction;
- repeat-upload idempotency and no duplicate active tickets;
- concurrent public registration during import;
- five independent authorized gate sessions;
- exactly one accepted result for a credential raced across all five gates;
- revoked, invalid, wrong-event, expired-session and network-loss behavior;
- dashboard/export reconciliation against confirmed server records;
- p50/p95/p99 latency and error rates under the agreed arrival profile;
- restart/failure recovery for API, dispatcher and worker.

A successful unit/integration suite is necessary but is not event-scale evidence.

## Logging and incident commands

Use the provider's log viewer for each named service and filter by request/job ID,
never personal values. With the restricted job-operator credential:

```sh
python -m app.worker.ops health
python -m app.worker.ops dead
```

Retry a dead job only after reconciling the destination and determining whether
the external effect occurred. Do not reset attempts or delete outbox rows.

Event-day alert candidates requiring explicit owners and thresholds:

- API readiness or database connection failure;
- p95/p99 scan latency and non-2xx rate;
- PostgreSQL saturation, lock waits and storage pressure;
- oldest unpublished outbox age, retry/dead jobs and worker heartbeat;
- ticket provider rejection/unknown delivery;
- domain ownership/TLS/routing evidence nearing expiry;
- dashboard freshness exceeding the UI contract.

Rotate the origin-auth secret as a coordinated edge/origin change during a
maintenance window, never during gate operations. Set the new value on the
origin, immediately replace the Worker secret, redeploy both, and run the valid
edge plus direct-origin-denial checks above. A mismatch intentionally causes
requests to fail closed. Retain the old value only long enough to roll back the
coordinated change, then revoke it from both secret stores. Rotate immediately
after suspected disclosure and inspect origin logs for denied requests.

## Backup, restore and rollback

Before every migration, take a provider-native PostgreSQL backup and record its
identifier. Enable encrypted point-in-time recovery after G-06 sets retention.
Enable bucket versioning/lifecycle only under the approved privacy schedule;
versioning must not defeat participant deletion indefinitely.

Rehearse restore into an isolated hostname and credentials:

1. Restore the database and storage snapshot to an isolated environment.
2. Keep public routing disabled.
3. Apply all due purge/deletion jobs before allowing any read traffic.
4. Verify Alembic head, RLS, login-role separation and a synthetic scan.
5. Record recovery time and recovery point; destroy the isolated copy under the
   approved test-data retention schedule.

For application rollback, route to the previous immutable image only when its
code is compatible with the current schema. Prefer a forward fix after a
migration reaches staging/production. Never downgrade a populated event
database without a reviewed data-loss plan. During an event, preserve confirmed
check-in writes and fail closed at the scanner if authority is uncertain.

## Go-live gate

Production remains **not verified** until all external blockers are resolved,
the exact deployed revision completes the synthetic rehearsal, backup restore is
observed, all five venue devices pass camera/network/session tests on the actual
venue networks, and named support owners approve the runbook. Cloudflare and
Render are candidates only until that evidence exists.
