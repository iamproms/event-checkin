# Event-scale rehearsal data

This directory prepares deterministic, synthetic input for the 3,000–5,000
participant event path. It is not production data and must not be connected to
a real email provider.

Generate an all-valid 5,000-row import and an error-heavy correction fixture:

```sh
python3 tests/load/generate_participants.py \
  --rows 5000 \
  --output /tmp/event-attendees-5000.csv

python3 tests/load/generate_participants.py \
  --rows 5000 \
  --inject-errors-every 50 \
  --output /tmp/event-attendees-errors.csv
```

The source references, names, email addresses and phone values are synthetic.
`example.test` cannot receive mail. Keep the staging delivery adapter in capture
or sink mode during load tests and assert delivery intents/jobs in PostgreSQL
instead of sending 5,000 messages.
Bulk imports require name and email; phone may be absent. Public self-registration
continues to require a valid E.164 phone number.

For an isolated local PostgreSQL rehearsal of the import pipeline and 5,000
ticket-issuance jobs, run the opt-in integration test. It creates its own
temporary test database and sends no email:

```sh
cd backend
LOCAL_DB_PASS=$(awk '/POSTGRES_PASSWORD:/ {print $2; exit}' ../compose.yaml)
RUN_EVENT_LOAD_TEST=1 PYTHONPATH=. \
  TEST_MIGRATION_DATABASE_URL="postgresql+psycopg://eventcheckin:${LOCAL_DB_PASS}@127.0.0.1:5433/postgres" \
  .venv/bin/pytest tests/test_event_operations_load_postgres.py -q --tb=short
unset LOCAL_DB_PASS
```

The test checks 25 bounded import chunks, 5,000 registrations and 5,000
idempotent `ticket.issue` jobs. This is a data-integrity rehearsal, not a
substitute for API latency or five-device venue testing.

## Required event rehearsal

Run these checks only after the M3-03/M4 contracts and migrations are deployed
to an isolated staging database:

1. Import 5,000 valid rows; verify the preview count before committing.
2. Import the error fixture; download the row-level errors, correct and re-run.
3. Upload the valid file twice; the second commit must not create another active
   registration or ticket for any contact.
4. Start public registration during import and confirm ordinary registration is
   responsive and independently enforces email/phone uniqueness.
5. Let the outbox and worker drain into a non-delivering transport; reconcile
   registrations, active tickets and delivery intents by event.
6. Redeem distinct synthetic tickets from five independent gate sessions at the
   target arrival rate.
7. Submit the same credential concurrently at all five gates. Exactly one
   transaction may return accepted; the other four must return duplicate.
8. Repeat for revoked, unknown, malformed and wrong-event credentials.
9. Compare the live dashboard and authorized CSV export to direct, read-only
   staging reconciliation queries. Missing data must not be presented as zero.
10. Restart an API instance and a worker during the test. Scan commits already
    confirmed by PostgreSQL must remain durable, and ambiguous client retries
    must not produce a second admission.

Record p50/p95/p99 request latency, error rate, database CPU/locks/connections,
queue age, worker retry/dead counts, and dashboard freshness. The technical
design targets remain acceptance criteria; this fixture alone is not load-test
evidence.

### Atomic five-gate race

After creating five real, event/gate-scoped staging sessions and capturing one
unused synthetic ticket credential, copy `race-config.example.json` outside the
repository, populate it and restrict it before running:

```sh
install -m 600 tests/load/race-config.example.json /tmp/event-scan-race.json
${EDITOR:-vi} /tmp/event-scan-race.json
SCAN_REHEARSAL_CONFIG=/tmp/event-scan-race.json \
  python3 tests/load/race_redeem.py
```

The driver uses the real `POST /api/v1/gate/redeem` contract, releases five
requests together and exits nonzero unless one response is `accepted` and four
are `duplicate`. It never prints the credential, cookies or CSRF values. Delete
the populated file immediately after the evidence is recorded. Run it only
against synthetic staging data; the credential becomes consumed.

## Safety checks

- Use a dedicated staging tenant/event and an empty, disposable staging inbox.
- Confirm the event hostname resolves only to staging before running.
- Keep production credentials out of the shell history and generated files.
- Never log QR credentials, session cookies, CSRF tokens or participant fields.
- Never interpret timeout/network loss as an accepted scan.
- Delete generated CSV/error/export artifacts after the rehearsal according to
  the approved test-data retention period.
