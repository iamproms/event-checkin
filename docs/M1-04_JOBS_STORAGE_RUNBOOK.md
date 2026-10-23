# M1-04 jobs and private files: contracts and operations

**Authority:** [approved M1-04 decisions](DECISIONS/M1-04_JOBS_FILES.md), [technical design](TECHNICAL_DESIGN.md), and [database design](DATABASE_DESIGN.md). M1-04 adds infrastructure, not imports, campaigns, exports, scans, or tenant provisioning.

## Transaction and trust boundaries

An authorized command calls `enqueue_job(session, ...)` inside its PostgreSQL business transaction. The helper inserts a `job_records` row and a matching `outbox_events` row before the caller commits. It never calls Redis. A duplicate `(tenant_id, job_type, idempotency_key)` returns the existing job only when event and retry contract match. The database has a unique key and composite tenant/job foreign key. Callers must use a server-authorized tenant session; RLS rejects a mismatched tenant.

The dispatcher uses the restricted `eventcheckin_dispatcher` login to lease an unpublished outbox row with `FOR UPDATE SKIP LOCKED`, commits the lease, publishes **only the job UUID** to Celery/Redis, then marks the row published. A crash or unknown publish result can cause duplicate delivery. An unpublished row is never discarded or marked permanently dead, and its lease expires for recovery. If Redis loses a message after acknowledgement, an aged PostgreSQL `pending` job with a published outbox row is republished. Redis failure affects dispatch but not the committed PostgreSQL command. Retry and recovery notifications have a 30-second database cooldown so a waiting worker cannot cause a broker flood.

A Celery worker receives the UUID, loads the authoritative job through the restricted metadata-only job role, derives tenant ID from the row, then establishes the existing transaction-scoped tenant context on the separate runtime login. The handler and `succeeded` transition commit together under the job row lock. Duplicate or concurrent execution cannot repeat a completed PostgreSQL effect. A running job with an expired lease is reclaimable; each claim counts toward the bounded attempt limit. Failures persist a fixed safe error code and enter `retry_wait` or `dead`. The dispatcher republishes due retries and expired leases from PostgreSQL. External services need their own destination idempotency contract; M1-04 claims at-least-once delivery, not exactly-once external effects.

`eventcheckin_jobs` has cross-tenant RLS access **only to job metadata**, with no outbox write, identity, registration, ticket, or private-object grants. `eventcheckin_dispatcher` can update outbox publication metadata and the job notification cooldown but cannot change job state or tenant. Neither can change a job's tenant ID or type. `eventcheckin_job_operator` is a distinct NOLOGIN role for dead-letter inspection and manual retry. All three roles have `NOBYPASSRLS` and do not own the tables. `job_records`, `outbox_events`, and `private_objects` have FORCE RLS. There is no public submission, upload, download, dead-letter, or retry route.

## File lifecycle

The only active purpose is `internal_test_artifact` in local/test. The internal test harness uses an authorized tenant transaction; the service rejects other environments, MIME types outside `text/plain` and `application/pdf`, and sizes above 5 MiB. Database constraints reinforce the type, size, and maximum 24-hour expiry. A presigned POST has a fixed private staging key, content type, size range and configurable lifetime (default ten minutes). After HEAD validation, the service copies the object to a distinct private final key and marks metadata available. Reusing the still-valid upload URL can alter only the staging key. Download authorization checks tenant RLS, purpose, state and expiry before issuing a presigned GET (default five minutes, clamped to the object expiry). A local/test sweeper deletes expired staging and final objects under server-derived tenant context; the local bucket also has a one-day expiry rule as orphan cleanup defense. Signed URLs are bearer URLs while valid; handle them as secrets and never log them.

Local/test object storage uses the versioned `rustfs/rustfs:1.0.1` image. The bucket initializer uses the already-built backend image and Boto3, so there is no separate object-storage client image to pull. It creates the private bucket and applies the one-day lifecycle rule, failing if either step is unavailable. The application's S3 endpoint, bucket, SigV4 path-style signing, and `STORAGE_*` configuration remain unchanged. RustFS's local single-node mode is test infrastructure, not a production provider decision. The old `object_data` volume is left untouched; RustFS uses a new `object_data_rustfs` volume because object-store data formats are not interchangeable. No existing local object data is migrated automatically.

No real personal data, application file purpose, production storage provider, region or production bucket credentials are approved. The internal test purpose has no HTTP route and must never be enabled in production. Future file-owning milestones must add explicit purpose, authorization, content inspection, maximum size, and retention contracts.

## Local startup and validation

From the repository root, without resetting volumes:

```sh
docker compose up --build -d db redis object-storage object-storage-init
docker compose run --rm role-setup
docker compose run --rm migrate
docker compose up --build -d api worker dispatcher storage-maintenance
docker compose exec db psql -U eventcheckin -d eventcheckin -c 'SELECT version_num FROM alembic_version'
curl --fail http://127.0.0.1:8000/health
```

When continuing from the shared M1-03 Compose project, start only the new storage services; do not restart PostgreSQL or the API:

```sh
docker pull rustfs/rustfs:1.0.1
docker compose build object-storage-init
docker compose up -d --no-deps object-storage
docker compose run --rm --no-deps object-storage-init
```

The final command must exit successfully before S3 tests run. `docker compose config --quiet` checks Compose syntax but does not prove the image can be pulled or that presigned POST, conditional copy, and lifecycle operations work. Validate those operations with the real object-storage integration test.

The operator credential is local-only. For health and dead letters, set `APP_ENV=local`, `DATABASE_URL` to the **restricted runtime** login, and `JOBS_OPERATOR_DATABASE_URL` to the separate operator login; then run `python -m app.worker.ops health` or `python -m app.worker.ops dead` in the backend environment. `python -m app.worker.ops retry <job-uuid>` is a deliberate operator action after checking whether the external destination already applied the effect. Do not run operator commands with the migration owner or API credential. Production operator provisioning and credential distribution remain under G-06.

For reproducible isolated tests, set `TEST_MIGRATION_DATABASE_URL` to a PostgreSQL migration login with temporary database and role creation rights, `TEST_REDIS_URL` to a local Redis database, and `TEST_S3_ENDPOINT`, `TEST_S3_BUCKET`, `TEST_S3_ACCESS_KEY`, and `TEST_S3_SECRET_KEY` to a private local S3-compatible bucket. Then:

```sh
cd backend
python -m pip install -e '.[dev]'
pytest -q
ruff check .
mypy app
```

The PostgreSQL fixture creates and drops only uniquely named temporary databases and logins. It tests `0004 → 0005 → 0004 → 0005`; the existing authentication fixture also covers fresh upgrade and downgrade through `0002`. Do not downgrade a populated development or production database for testing.

## Recovery indicators and actions

`ops health` reports counts for `pending`, `running`, `retry_wait`, `dead`, unpublished outbox rows, expired leases and oldest unpublished age. Growing unpublished age indicates dispatcher or Redis trouble; inspect dispatcher and broker health, then restart those processes. The outbox replays automatically after its lease/backoff expires. Growing expired leases indicates stuck workers or long handlers. Check worker health and database locks before adding capacity. Dead jobs require inspection, destination reconciliation and explicit operator retry. Do not purge unpublished outbox rows or reset attempts to conceal an outage. Keep queue, job and storage identifiers free of personal data.

M1-04 does not define alert thresholds or a production paging target; those remain part of M1-01/G-06 operations hardening. The API `/ready` remains authoritative for API/PostgreSQL availability; a Redis outage must not make scan transactions depend on queue health.
