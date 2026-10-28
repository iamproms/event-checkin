# Rollback and recovery

## Principles

- Stop new external effects before changing data: pause frontend traffic,
  ticket sending/import actions, dispatcher and workers as appropriate.
- Never interpret a timeout as a failed admission or email. Reconcile the
  authoritative database/provider state before retrying.
- Roll application code forward/back to a known image before considering a
  schema downgrade. Migration `0013` refuses downgrade once new notice/import
  evidence exists; that guard is intentional.
- Preserve logs, release SHA, request/job IDs and database restore point without
  copying participant or credential data into tickets/chat.

## Application rollback

1. Incident commander declares rollback and records UTC time/scope.
2. Disable Vercel production promotion or route to the last known-good frontend.
3. Pause Render dispatcher and Celery workers if the incident can create
   duplicate external effects. Keep PostgreSQL available for reconciliation.
4. Roll Render API, worker and dispatcher to the same known-good Git/image SHA.
   Do not mix schemas or worker/API versions outside the documented compatibility
   window.
5. Restore Vercel to the matching deployment. Re-run readiness, authentication,
   tenant-isolation and one synthetic gate smoke test.
6. Inspect job health. Retry dead jobs only through the restricted operator
   command after checking whether Brevo or another destination already applied
   the effect.

## Migration failure

Before migration: create a Supabase restore point/PITR marker and schema-only
dump, record `alembic current`, stop writes, and test the exact image against a
restored staging copy.

If migration fails before completion:

1. Keep the new application version undeployed and capture the sanitized error.
2. Inspect transaction state and `alembic_version`; PostgreSQL transactional DDL
   should leave the failed revision unapplied, but verify rather than assume.
3. Correct forward in a new reviewed migration or restore to the pre-migration
   point. Do not edit a migration already applied to any shared environment.

If migration succeeds but the application fails:

1. Prefer application rollback while retaining the forward-compatible schema.
2. Run `alembic downgrade 0012_shared_event_release` only after proving no
   `0013` notice drafts/approvals/import authorization evidence exist and after
   a fresh backup. The migration itself will abort if evidence exists.
3. If evidence exists or integrity is uncertain, restore into a new Supabase
   project/database from the pre-migration point, validate it, rotate database
   credentials, and cut services over during a declared outage.

## Admission incident

- Pause the affected gate/event, not the whole database, when possible.
- Query authoritative accepted attempts and ticket status using a restricted,
  read-only operator path. Client screenshots/local QR validation are not proof.
- For ambiguous network results, resubmit the same credential online: the
  unique accepted-ticket constraint yields accepted once, duplicate thereafter.
- Never delete or rewrite check-in attempts during the event. Correct reports
  through an auditable post-incident procedure.

## Email incident

- Stop new bulk send actions and pause ticket-delivery workers if provider state
  is ambiguous. Ticket issuance can remain separate from delivery.
- Reconcile each durable delivery intent against Brevo message ID/webhook logs.
  The intent UUID is the idempotency key. A provider duplicate response is not a
  reason to send with a new key.
- Rotate a compromised API key or webhook token, update Render/Brevo together,
  and verify one synthetic callback. Do not rotate ticket encryption keys as an
  email recovery step.

## Credential/key recovery

- Origin-auth secret: update Render first with a short overlap/maintenance
  window, update Vercel immediately, deploy both, then test direct-origin denial.
- Database password: rotate one least-privilege login at a time and redeploy only
  its consumers. Confirm no process uses the migration owner.
- Auth/ticket encryption keys: use the versioned rotation procedure and retain
  old decrypt/verify keys until all dependent sessions/tickets expire. Losing
  the ticket keyring invalidates outstanding tickets; restore it from the
  approved secret backup rather than silently replacing it.

## Recovery acceptance

Traffic may resume only when `/ready`, database/RLS probes, worker/dispatcher
health, one synthetic auth flow, one accepted+duplicate scan, and queue/email
reconciliation all pass. Document data loss window (if any), unresolved jobs,
attendee impact and follow-up owner.
