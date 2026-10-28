# Production smoke tests

Run only after the backend, workers, email callback and frontend are deployed at
the same approved commit. Use a dedicated synthetic organization/event and
`example.test` data. Do not send bulk mail or run production load tests.

Record UTC time, release SHA, operator, expected/actual result and a safe request
ID for every step. Never record a cookie, CSRF token, password, QR credential or
participant field.

## Infrastructure and boundary

1. `GET https://RENDER_ORIGIN/health` returns `200 {"status":"ok"}`.
2. `GET https://PUBLIC_HOST/ready` returns 200 with API/database ready. Treat
   worker `not_configured` as informational and separately verify Render worker
   and dispatcher state.
3. Direct Render-origin `/api/v1/auth/csrf` without the private header returns
   404. `/ready` may remain public for Render health checks.
4. Unknown public Host and hostile Origin mutations fail closed; no permissive
   CORS header appears.
5. Response headers include CSP, `X-Content-Type-Options: nosniff`, no-referrer
   and the expected permissions policy. Static fingerprinted assets are
   immutable; authenticated/API responses are `no-store`.

## Authentication and isolation

1. Platform and organizer login require CSRF; invalid credentials disclose no
   account state. Platform MFA is enforced.
2. Session cookies are Secure, HttpOnly, host-only and SameSite=Strict.
3. Create synthetic organizations A and B. Confirm A's organizer cannot read B's
   events, registrations, tickets, imports or attendance; confirm platform
   sessions cannot read tenant participant records.
4. Revoke a test session and grant; subsequent requests fail immediately.

## Organization and privacy administration

1. Search the directory by name and organizer email; verify pagination, empty
   state, detail serialization and safe error state.
2. Draft a synthetic notice; verify version, creating actor/time and inactive
   state. Missing confirmation/reference must fail.
3. Approve it and verify approving actor/time/reference. Attempted content edit
   must fail. Activate it and verify the prior active version deactivates.
4. Confirm a normal organizer cannot draft, approve or activate a notice.
5. Attempt public registration before an active approved notice: fail. Repeat
   after activation with matching notice version: succeed.

## Import, tickets and email

1. Preview an email-only synthetic CSV with a duplicate and invalid row. Verify
   counts and CSV-safe error export. Repeat upload; verify idempotent reuse.
2. Validate mappings. Commit must remain disabled until explicit authority is
   confirmed. Repeating commit must not duplicate registrations/jobs.
3. Issue tickets, then send exactly one synthetic ticket to an approved test
   inbox. Verify the QR PNG attachment, sender identity and event/timezone copy.
4. Confirm delivery intent progresses queued -> sending -> sent -> delivered
   after the authenticated Brevo callback. Replay the callback; state remains
   stable. Simulate a bounce in staging and verify bounced/error tracking.

## Gate and reporting

1. Assign one scanner to the synthetic event/gate. The device must show no
   participant identity and must never infer admission from local QR decoding.
2. Redeem one valid credential: only `accepted/ACCEPTED` displays “Admission
   confirmed.” Repeat: `duplicate/DUPLICATE_ADMISSION`, no admission.
3. Verify revoked, invalid, event unavailable, gate unavailable, not-open,
   closed and incomplete-window responses and messages.
4. Race one unused synthetic credential across five authorized gate sessions:
   exactly one accepted and four duplicate results.
5. Compare live attendance and authorized CSV export with database-backed
   counts; CSV cells beginning `=`, `+`, `-` or `@` must be escaped.
6. Remove network during a scan. The UI must say “Do not admit”; retry the same
   credential after recovery and accept only the server result.

## Background and rollback signal

1. `python -m app.worker.ops health` reports no dead jobs, expired leases or
   sustained unpublished outbox backlog.
2. Restart one API and one worker while synthetic jobs exist. Readiness recovers,
   leases retry safely, and no admission/delivery duplicates appear.
3. Verify Render, Vercel, Supabase and Brevo alert delivery to the event support
   channel.
4. If any security boundary, migration, admission invariant or rollback check
   fails, stop and follow [ROLLBACK_AND_RECOVERY.md](ROLLBACK_AND_RECOVERY.md).
