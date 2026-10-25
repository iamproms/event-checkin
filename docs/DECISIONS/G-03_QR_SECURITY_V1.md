# G-03 — QR credential security v1

**Status:** Approved for implementation, 2026-10-25.

## Decision

An entry QR contains only an opaque credential in the form `v<key-version>.<random-value>`. The random value is 32 bytes from the operating-system cryptographic random source and contains no tenant, event, registration, contact, route, or analytics data. Validation is online and server-authoritative; a QR is not a self-contained attendee assertion.

PostgreSQL stores an HMAC-SHA-256 verification digest and an authenticated-encrypted resend copy. Digest and encryption keys are independently derived with HKDF from the versioned deployment key. AES-256-GCM binds the resend copy to tenant, event, registration, and ticket identifiers as additional authenticated data. The master keyring is injected from a secret store and is never persisted in the application database.

New tickets use the configured active version. Rotation adds a new version, changes the active version, and retains old keys while any active ticket needs verification or resend. Removing an old key makes its tickets unverifiable and unrestorable, so removal requires an inventory and reissue plan. Reissue revokes the prior credential before creating a replacement. Revoked or used tickets cannot be reactivated, and credential material is immutable after insert.

Only a keyed digest comparison inside a tenant- and event-scoped database transaction may identify an active ticket. APIs, queue messages, logs, URLs, analytics, and provider metadata must not contain the raw credential. Gate redemption and one-use atomicity remain M4-02; the M3-02 verification interface returns a ticket identifier, never attendee identity.

## Operational requirements

- Production keys must be independently generated 32-byte secrets stored in the approved regional secret manager. The checked-in local value is test data only.
- Backup, restore, rotation, compromise response, access logging, and key destruction require the G-06 provider/region decision.
- QR credentials are bearer entry evidence. Email and UI copy instruct recipients to keep them private.
- PDF ticket output is not implemented because no PDF format was approved.
