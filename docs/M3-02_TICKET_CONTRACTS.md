# M3-02 ticket and delivery contracts

## Lifecycle

An accepted registration enqueues `ticket.issue` with the registration UUID as its idempotency key. The worker locks that registration, verifies the published event, and creates at most one active ticket. Resend decrypts and sends the same credential. Reissue revokes the active ticket and atomically creates a new credential. Revoke is terminal. The database prevents multiple active tickets and prevents terminal ticket reactivation or credential mutation.

Authorized tenant owners/admins and event-assigned organizers/managers may inspect status and request `resend`, `reissue`, or `revoke` through `/api/v1/events/{event_id}/registrations/{registration_id}/ticket`. Resend and reissue require a still-published event and active registration; revocation remains available after closure or cancellation. Mutations require the existing session and CSRF contract. Gate roles and platform actors have no default participant/ticket access. Participant listing and support search remain M3-04 rather than being introduced here.

## Delivery

Each intentional send has a durable delivery intent and an idempotent `ticket.deliver` job. The intent UUID is the provider idempotency key. `sending`, `sent`, `delivered`, `failed`, and `bounced` are distinct states. A provider error commits the safe `DELIVERY_UNAVAILABLE` state before the job enters retry backoff; no exception or contact is persisted. Retry reuses the same intent and credential. A new admin resend creates a new intent but not a new ticket.

The provider-neutral message contains the rendered QR, organizer display name, configured sender display name, published primary color, published logo when private storage is available, event name, local schedule and entry/help instructions. The sender address remains deployment/provider configuration; tenant branding cannot choose or verify it. A missing logo or storage outage falls back to text branding and does not block ticket delivery. HTML values are escaped and the sender display name is validated before header construction. No raw credential appears in URLs, logs, job payloads, database provider metadata, or status responses. The local in-memory and SMTP adapters are development/test transports. Local SMTP has a stable `Message-ID`, but unlike an approved production adapter cannot guarantee provider-side idempotency after an ambiguous network failure.

No provider callback route is enabled because no provider/signature contract is approved. A future adapter must authenticate callbacks, bind them to the stored provider message ID and tenant-scoped intent, tolerate duplicates/out-of-order events, and reject terminal-state regression.
