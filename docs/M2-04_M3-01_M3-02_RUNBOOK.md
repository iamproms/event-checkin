# M2-04 / M3-01 / M3-02 operations runbook

## Local-only setup

Apply migrations `0008_tenant_branding`, `0009_public_registration`, and `0010_ticket_delivery` before new application code receives traffic. The Compose values are deterministic local fixtures, not production secrets. Install the backend project so Pillow and QR rendering dependencies are present, start PostgreSQL, Redis, object storage, Mailpit, API and worker, then use a verified local tenant hostname.

No migration installs a privacy notice. Tests insert synthetic copy directly into their temporary database. Before any real collection, obtain product-owner/legal approval, retain the approval reference outside the application, insert an immutable notice row with the exact body, lawful basis, digest and approval time, and activate only one version per tenant. Rehearse replacement in staging; never edit an approved version.

## Branding recovery

Logo upload decodes one PNG/JPEG/WebP frame and stores a stripped PNG in the private `retained/tenants/{tenant}/branding` prefix. This prefix is not covered by M1-04's one-day local test-artifact lifecycle. Malformed, animated, mismatched, oversized and SVG content is rejected. Publication validates both theme contrasts, serializes on the tenant row, and appends a version/audit row. Restore publishes a new version derived from history. If storage is unavailable, text branding remains readable and publication of an unavailable logo fails. Historical logo objects must remain while referenced by restorable versions; object cleanup needs a reference inventory.

## Registration and ticket recovery

- Redis unavailable: registration fails closed. Restore Redis and retry; do not bypass throttling.
- Notice, keyring, transport, or issuance flag unavailable: the public page reports registration unavailable. Do not enable real collection until all gates are satisfied.
- Duplicate contact: return the neutral confirmation; an authorized organizer may resolve support through the later M3-04 participant workflow. Do not merge or replace automatically.
- Issuance job retry/dead: inspect only through the restricted job-operator role. Fix the cause, confirm no active ticket exists, then use the established dead-job recovery command.
- Delivery failure: the intent records a safe failure code and job retry state. An approved provider adapter must reconcile by intent id before retry. Admin resend creates a new intentional delivery; reissue is reserved for credential compromise/loss and invalidates the prior QR. Ticket rendering reads the published logo from private storage; if that read fails, delivery continues with the organizer name and accessible published color rather than delaying entry credentials.
- Key rotation: add the new secret version everywhere, deploy readers, switch the active version, then reissue or retire all old active tickets before deleting an old key. Loss of a retained key makes resend and verification impossible.

## Production blockers

Production/staging activation remains blocked by G-06 decisions for edge/hostname, data and secret-manager region, object storage, transactional email provider, verified sender/domain, callback signing, retention/DPA, and approved credentials. The final privacy notice and lawful basis also require product-owner approval. No real external email, callback, real attendee collection, staging QR redemption, or data-region compliance is demonstrated by local adapters. M2-02 Paystack billing remains deferred and incomplete.

PDF tickets are omitted because no format was approved. Online atomic gate redemption remains M4-02. Participant search/support UI remains M3-04.
