# G-08 — Event-first product experience and theme preference

**Status:** Approved by product owner, 2026-10-26.

**Applies to:** the shared frontend product architecture and the urgent November 1, 2026 event delivery.

## Decision

The immediate release path is the connected operational sequence:

1. organizer authentication and MFA;
2. event configuration and publication;
3. public registration and bulk participant import;
4. transactional QR ticket issuance and delivery;
5. scoped gate-staff access and online, server-confirmed redemption;
6. confirmed live attendance; and
7. authorized event attendance export.

Billing, campaigns, advanced analytics, additional platform operations, and nonessential integrations are deferred. Their navigation may remain visible only when it communicates a truthful unavailable or coming-soon state. Event-critical destinations must not use placeholder data or simulated success.

The product retains the G-07 Quiet Precision foundation: Inter, warm-neutral surfaces, evergreen actions, independent semantic colors, 4px control radii, 8px structural radii, restrained elevation, and reduced-motion support. The application composition uses a framed-sheet shell for operational work and an event-arrival timeline as its recurring product signature.

Authentication uses a split editorial composition. The current repository contains an original, code-drawn venue treatment because no approved, appropriately licensed event photograph is stored in the project. It must not be represented as photography. A later image substitution requires a locally stored licensed source, license record, crop review, and light/dark readability review; unlicensed reference imagery and third-party hotlinks are prohibited.

## Theme preference amendment

This decision supersedes only G-07's first-visit theme behavior.

- The preference has three values: `system`, `light`, and `dark`.
- First visit uses `system`.
- `system` follows `prefers-color-scheme`, including subsequent operating-system changes.
- Explicit `light` or `dark` choices persist locally and do not follow system changes.
- The resolved theme is applied before React mounts to avoid a wrong-theme flash.

All other G-07 visual and accessibility constraints remain in force.

## Operational integrity

### October 27 event-release amendment

The event uses external registration and an email-first CSV import. Newly created events default to `import_only`. The organizer can still select the existing public mode, but public registration is no longer a release prerequisite. Import-only publication requires a check-in window and an enabled gate; it does not require a public registration window. Imported registrations remain subject to an active approved notice and lawful-basis attestation.

Import-only CSV commits create registrations without sending tickets. The organizer explicitly queues idempotent ticket issuance, reviews the message, then queues the first delivery for each issued imported ticket. Existing public-registration issuance remains automatic. A provider-accepted email is displayed as `sent`, never as proof of inbox delivery. In local development Mailpit is the only active transport; staging and production delivery remain disabled until an approved provider and sender are configured.

Shared-host organizations are active tenants without a per-organization domain record. The platform host provides the common sign-in and authorized tenant workspace. A short-lived signed, HttpOnly tenant-context cookie supplies only a routing hint; password verification, tenant-bound session lookup, membership, MFA, FORCE RLS, event assignment, CSRF, and audit remain authoritative. Platform sessions alone never authorize tenant API access. The first-owner invitation binds its token to the tenant; its link carries a tenant ID solely to find that invitation. Existing verified custom-domain routing is preserved. This amendment replaces hostname-only tenancy for authenticated shared-host staff requests, not for public registration or custom-domain requests.

The shared-host creation endpoint accepts organization name and organizer email, generates identifiers, and records an idempotency key. The optional first-event name is retained as a setup suggestion; the organizer supplies a real schedule before creating the event. Local account-setup email is accepted by Mailpit synchronously. A durable background invitation transport and approved production email provider remain release blockers; the UI reports a failed transport and offers a controlled resend without showing raw tokens.

- Public and imported registrations converge on the same registration and ticket lifecycle.
- Imports never silently overwrite registrations, create duplicate active tickets, or bypass privacy and transactional-email activation gates.
- A gate UI never reports admission until an authoritative server transaction commits redemption.
- Redemption is online-only and atomic across gates. Network failure is an unknown outcome, never success.
- Scanner responses expose no participant identity unless a later approved policy explicitly permits a minimal label.
- Attendance metrics come from committed check-in records and expose freshness; absent data is not rendered as zero.
- Exports are event-scoped, authorized, auditable, and limited to fields permitted for the requesting role.

These rules preserve FORCE RLS, hostname-derived tenancy, composite tenant/event scope, MFA, CSRF, secure host-only sessions, ticket secrecy, and the approved M3-02 resend/reissue/revoke semantics.

## Activation gates

Production use remains blocked until all of the following are verified:

- approved privacy notice and lawful basis for imported contacts;
- approved transactional sender/domain and delivery-provider configuration;
- deployment credentials, verified domains, HTTPS, secrets, migrations, workers, storage, backups, and recovery checks;
- representative 3,000–5,000-registration load testing and five-gate concurrent-redemption testing; and
- a real-device rehearsal with venue connectivity and escalation procedures.

Passing automated tests is necessary but does not by itself satisfy these activation gates.
