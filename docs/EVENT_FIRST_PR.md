# Event-first shared-host release

## Summary

- Adds simple organization creation with an idempotent platform request, secure owner invitation, and shared-host tenant routing without changing custom-domain verification.
- Unifies staff sign-in around server-authorized platform, organizer, and gate contexts. Adds shared-host password recovery for active tenant staff.
- Adds import-only events and email-only CSV import; separates registration import, QR issuance, and transactional ticket sending.
- Adds configurable gate management, gate staff directory/reassignment/revocation, online atomic redemption, live attendance, and privacy-scoped CSV export.
- Keeps billing and campaigns visibly deferred. Production email remains disabled until an approved provider, sender, callbacks, and privacy basis are configured.
- Includes migration 0011 and 0012, deployment examples, a staging runbook, route/capability documentation, load tools, and representative screenshots.

## Validation

- Backend full suite after migration 0012: 129 passed, 1 opt-in load test skipped; targeted two-tenant scheduler and staff reassignment cases then passed 2/2.
- Opt-in 5,000-row email-only import and explicit issuance rehearsal: passed in 48.10 seconds without sending mail.
- Frontend Playwright: 35 passed; desktop/mobile captures and automated accessibility cases included.
- Ruff, mypy, TypeScript, ESLint, production frontend build, and Git whitespace checks passed.
- Local HTTPS smoke: migration 0012 verified; API, database, worker, dispatcher, domain/storage maintenance, and HTTPS running.

## Release gates

- This PR is for review; no production deployment or real-attendee mail send is claimed.
- Select and approve a data region, providers, privacy notice/lawful basis, transactional email sender/callback/idempotency contract, backup retention, and public HTTPS hostname.
- Complete the real browser journey with synthetic identities and test recipients, then rehearse physical cameras and all configured gates on venue networks.
- The local Mailpit transport records acceptance only; it cannot prove inbox delivery.

See [the runbook](EVENT_STAGING_DEPLOYMENT_RUNBOOK.md) for deployment and rehearsal steps.
