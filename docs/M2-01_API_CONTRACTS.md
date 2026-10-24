# M2-01 API contracts — provisional implementation, version 1

These contracts implement the approved M2-01 foundation. The platform routes require the configured dedicated platform hostname, a platform MFA session, a current `tenant.provision` grant, and CSRF for writes. Tenant routes resolve the canonical Host first, then verify the staff session and membership. A request body or URL tenant ID never establishes authority.

All responses containing authentication state or domain proofs use `Cache-Control: no-store`. Errors use `detail: {code, message}`. DNS proofs are returned once at creation; only their digests are retained. Authentication uses the existing G-02 Secure, HttpOnly, SameSite cookie and CSRF conventions.

| Method | Path | Result |
|---|---|---|
| GET | `/api/v1/platform/auth/csrf` | CSRF token for platform writes |
| POST | `/api/v1/platform/auth/login` | `{state: "mfa"\|"enroll"}`; opaque challenge cookie |
| POST | `/api/v1/platform/auth/mfa/enroll` | One-time authenticator setup secret, challenge required |
| POST | `/api/v1/platform/auth/mfa/verify` | `{state:"session", recovery_codes:[...]}`; rotates into session cookie |
| GET | `/api/v1/platform/auth/session` | User ID, email, effective `tenant.provision` permission |
| POST | `/api/v1/platform/auth/logout` | Revokes server session and clears cookies |
| POST | `/api/v1/platform/tenants` | Name and lowercase slug → tenant ID, fallback host, proof |
| GET | `/api/v1/platform/tenants/{tenant_id}/domains` | Domain states for authorized platform review |
| POST | `/api/v1/platform/tenants/{tenant_id}/domains/{domain_id}/check` | Queues durable reconciliation; job ID |
| POST | `/api/v1/platform/tenants/{tenant_id}/domains/{domain_id}/renew` | Rotates proof for a nonactive domain; one-time DNS value |
| POST | `/api/v1/platform/tenants/{tenant_id}/domains/{domain_id}/activate` | Activates after current proof, TLS, edge and smoke checks |
| POST | `/api/v1/platform/tenants/{tenant_id}/domains/{domain_id}/deactivate` | Deactivates only with a working fallback |
| POST | `/api/v1/platform/tenants/{tenant_id}/owner-invitations` | Sends a 48-hour first-owner invitation, with platform actor provenance |
| POST | `/api/v1/platform/tenants/{tenant_id}/owner-invitations/reissue` | Revokes the unaccepted initial-owner invitation, then sends a new 48-hour single-use link to the same address; the platform actor and both invitation IDs are audited |
| GET | `/api/v1/domains` | Own tenant's domain states after membership authorization |
| POST | `/api/v1/domains` | Requested hostname → claim ID and one-time DNS proof |
| POST | `/api/v1/domains/{domain_id}/check` | Queues check for own tenant only |
| POST | `/api/v1/domains/{domain_id}/renew` | Rotates proof for own nonactive custom domain |

Domain status fields are `ownership`, `tls`, and `routing`, plus `serving` (the current PostgreSQL public-routing resolver result, not a new persisted state). `serving=false` takes precedence over an `active` record in UI messaging, including tenant suspension or closure. `tenant.domain.manage` is required for ordinary claims; `tenant.domain.recover` is limited to suspended owner fallback-host recovery. Platform activation is never delegated to a tenant role.

The platform API is a narrow provisioning surface. It does not expose general grant management, participant data, public tenant sign-up, billing, or sender-domain verification.
