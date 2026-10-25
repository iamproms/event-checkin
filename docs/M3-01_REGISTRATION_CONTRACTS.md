# M3-01 public registration contracts

## Public API

`GET /api/v1/public/events/{slug}` resolves the tenant exclusively from the validated request authority and returns a published event, its immutable current form version, registration availability, and the active approved privacy notice. Unknown hosts and unavailable events use a non-enumerating public error.

`POST /api/v1/public/events/{slug}/registrations` accepts `full_name`, `email`, `phone`, `custom_answers`, `form_version`, `notice_version`, `notice_acknowledged`, and optional `marketing_opt_in`. Extra fields, including a client tenant identifier, are rejected. Browser origins must match the canonical tenant origin. The response is the same neutral 202 message for a new registration and an independently duplicated email or phone.

Email domains use IDNA ASCII form and the mailbox is normalized consistently. Phone input must supply an international `+` number and is persisted as E.164. The service does not guess a country. The published JSON form schema is an allowlist; unknown keys, invalid options, control characters, oversized values, and missing required values fail validation.

## Atomic effect and abuse boundary

One tenant-scoped PostgreSQL transaction verifies the published event and half-open registration window, locks the current form/notice evidence, inserts the registration and consent, and enqueues the idempotent `ticket.issue` job plus outbox row. FORCE RLS and composite tenant/event keys remain authoritative. Partial unique indexes independently protect active normalized email and phone.

Public submission is fail-closed when Redis throttling, approved notice evidence, or ticket issuance readiness is unavailable. Remote client IP is accepted only as one edge-overwritten `X-Forwarded-For` value from a configured ingress peer; chains and direct-origin traffic fail closed. Redis stores only an HMAC of the address. Application logs must not include request bodies, contacts, consent text, QR credentials, or provider payloads.

Real attendee collection is blocked until the final G-04 notice/lawful basis is approved and installed. Registration expiry and participant purge continue to use event end plus 90 days.
