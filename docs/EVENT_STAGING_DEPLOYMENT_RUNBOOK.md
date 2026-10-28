# Event staging deployment and rehearsal

**Status:** configuration prepared; no external resources created.
**Provider shape:** Vercel frontend, Render API/workers, Supabase PostgreSQL,
Brevo transactional email, GitHub source control.

Staging must mirror the production trust boundaries. Do not use the retired
combined Cloudflare/Caddy frontend topology for Reverb 5.0. Vercel serves the
Vite build and same-origin proxy Functions; Render's Caddy container protects
the API origin and forwards only authenticated edge traffic to Uvicorn.

Use `.env.staging.example`, `frontend/.env.production.example` and
`PRODUCTION_DEPLOYMENT_PLAN.md`. Staging needs distinct credentials, database
roles, Redis, storage, domains, Brevo key/sender and webhook token; never reuse
production secrets or real participant data.

## Deploy

1. Provision an isolated Supabase project and create the least-privilege login
   roles from `ops/deploy/supabase_roles.sql.example`.
2. Use TLS verification with the Supabase CA. Take a restore point, then run the
   exact candidate image's `ops/deploy/migrate.sh`. Confirm the single head
   `0013_privacy_notice_workflow` and FORCE RLS.
3. Create Render API, two workers, one dispatcher, Redis and a job-health cron
   from the production example with staging names/plans. Automatic deploys stay
   off for rehearsals.
4. Configure a verified Brevo staging sender and authenticated callback. Send
   only to an approved test inbox/capture address.
5. Deploy `frontend` to a Vercel preview/staging project with its own public
   domains and the matching Render origin secret.
6. Run all cases in `PRODUCTION_SMOKE_TESTS.md` with synthetic data.

## Event-scale rehearsal

Generate the 5,000-row fixtures documented in `tests/load/README.md`. Use a
non-delivering/capture email setup for the bulk stage. Exercise five independent
gate sessions and use `tests/load/race_redeem.py` for exactly one accepted and
four duplicate results. Record p50/p95/p99 scan and API latency, error rate,
database saturation/locks, queue age, retries/dead jobs and Vercel/Render
failover behavior.

The automated 5,000-row PostgreSQL test proves bounded 200-row chunks and
idempotent job creation. It does not prove internet, provider, browser/device or
venue performance.

## Exit criteria

- Full CI and browser suite green on the candidate SHA.
- Restore rehearsal completed and timed.
- Tenant isolation and platform/organizer authorization probes pass.
- Brevo idempotency, QR attachment, callback and failure tracking pass.
- Five-device gate rehearsal meets the approved latency/error SLO.
- Operations, privacy, security and incident owners sign the production
  environment checklist and remaining-risk register.

Follow `ROLLBACK_AND_RECOVERY.md` for any failed migration, admission ambiguity,
queue backlog or email-provider incident.
