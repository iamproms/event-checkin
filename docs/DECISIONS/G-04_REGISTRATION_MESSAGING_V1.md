# G-04 — Registration privacy and transactional ticket messaging v1

**Status:** Technical contract approved, 2026-10-25. Final notice text and lawful basis are not approved for real attendee collection.

## Decision

Public registration records the exact approved privacy-notice version, SHA-256 content digest, lawful-basis evidence, acknowledgement time, source, and optional marketing choice. Approved notice content is immutable. Activating a replacement notice does not rewrite earlier evidence.

Marketing consent is separate, optional, unchecked by default, and never an eligibility condition. M3-01/M3-02 do not send marketing. Ticket issuance, delivery, resend, and delivery-help messages are transactional messages necessary to fulfil registration. They must not contain promotional content or feed a campaign audience without a separately approved basis.

Public duplicate-contact outcomes are deliberately neutral. The service does not merge, replace, or disclose an existing registration. Independent database constraints enforce one active email and one active phone per event under races.

Bulk import records the active approved notice version and an operator-attested lawful basis as import evidence. Its `acknowledged_at` is null: importing a row is never represented as attendee acknowledgement. The import service rechecks the active notice before each background chunk and sets marketing opt-in to false. The event operator remains responsible for the separately approved notice delivery procedure before transactional tickets are sent to imported contacts.

## Activation gates

No notice is seeded by migrations. Real registration remains fail-closed until the product owner approves the final notice and lawful basis and an accountable operator installs an immutable active notice version. Synthetic notices may be used only in test databases.

Production ticket email remains disabled until G-06 approves a transactional provider, verified sender/domain, callback authentication contract, data-processing region, retention terms, and credentials. A production adapter must use each delivery-intent UUID as the provider idempotency key and authenticate callbacks before changing delivery state. Local SMTP and the in-memory transport are test facilities and do not prove external delivery.
