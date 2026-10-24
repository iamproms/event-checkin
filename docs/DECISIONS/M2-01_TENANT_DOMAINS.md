# M2-01 — Tenant provisioning and web domains

**Status:** Approved product boundaries (2026-10-24); production activation remains gated by G-06.

This record implements D-01 and F-01/F-13/N-03/N-08. G-02 remains authoritative for staff identity, invitation lifetimes, MFA, and sessions. G-07 remains authoritative for UI foundations.

## Authority and trust

- Platform administration uses a dedicated configured host, a separate MFA-verified opaque session, an active `tenant.provision` grant, and a restricted control-plane database role. A tenant session or hostname cannot authorize platform operations. The control-plane role has no participant-table privileges or `BYPASSRLS`.
- A one-time operator command establishes the initial platform actor and grant. It has a distinct bootstrap database role, records an audit event, and has no HTTP endpoint. Further grants require a reviewed platform-administration contract; M2-01 does not provide a general grant-management API.
- The bootstrap database login may execute only a singleton-consuming function; it cannot insert users, credentials, grants, or audit rows directly. Domain reconciliation and scheduling use separate restricted database roles.
- Tenant owners/admins can request web-domain claims and inspect their own domains. Only a platform actor can activate a domain. The last working route cannot be deactivated without an active fallback route.
- Every tenant gets a platform-owned fallback hostname. `provisioning` is not ordinary public routing. `suspended` denies ordinary public routing; only an owner on the fallback host may use the limited recovery flow. `closed` denies normal tenant routing. No billing suspension or data-deletion behavior is implied.

## Web-domain contract, version 1

Ownership: `pending`, `checking`, `verified`, `failed`. TLS: `pending`, `issuing`, `active`, `failed`. Routing: `reserved`, `ready`, `active`, `deactivated`. The values are separate so a verified DNS claim cannot imply a valid certificate or active route. A fallback domain is platform controlled and has its own recorded proof and edge checks. Verification and TLS observations have expiry timestamps; an expired observation is not an activation predicate.

| State | Label | Tone | Instruction |
|---|---|---|---|
| Ownership pending/checking | Verify ownership | information | Add the displayed DNS proof and request a check. |
| Ownership verified | Ownership verified | success | Wait for certificate and routing checks. |
| Ownership failed | Ownership needs attention | warning | Correct the DNS proof and retry. |
| TLS pending/issuing | Securing domain | information | Wait for certificate issuance. |
| TLS failed | Certificate needs attention | danger | Check DNS and retry certificate setup. |
| Routing reserved/ready | Awaiting activation | information | A platform administrator must approve activation. |
| Routing active | Domain active | success | This hostname can serve the tenant. |
| Active record with expired safety predicate | Domain unavailable | danger | Use the fallback route and request a check. |
| Routing deactivated | Domain inactive | warning | Use the fallback hostname or request recovery. |

Activation requires a fresh ownership observation, valid TLS, configured edge mapping, passing smoke check, an eligible tenant (provisioning for its first fallback; active for custom domains), and platform authorization in the same guarded transition. Revocation, ownership loss, certificate loss, and tenant suspension immediately remove ordinary routing eligibility. Reconciliation is idempotent and rechecks database state before an external action. Job messages contain only job IDs.
An unactivated or deactivated claim can rotate its DNS proof through an authorized renewal action. The former proof no longer verifies it. Active routes require controlled deactivation before rotation. A 48-hour initial claim window does not terminate an active route that continues to pass fresh ownership checks.
Current smoke evidence is limited to 15 minutes; stale evidence removes routing eligibility. First-owner invitation delivery failures revoke the attempted link, and a platform actor can revoke and reissue a still-pending invitation to its original address with an audit trail.

## Hostname reservation policy

An expired, unverified custom-domain claim remains globally reserved. Expiry stops verification and activation; it does not automatically release the hostname for another tenant. The current owner may renew the proof. Cross-tenant reassignment requires a separately approved, attributable operator process and is outside M2-01. This preserves claim history and prevents automatic takeover from a stale or dangling DNS record.

Web-domain verification never verifies `tenant_branding.sender_domain` or authorizes email sending. Sender-domain verification remains G-04 work.

## Production gates

G-06 must approve the edge/custom-hostname and certificate provider, its credentials and region, a staging hostname and owned DNS zone, and the data region. Production mail and an approved versioned compromised-password corpus remain required for first-owner onboarding. A real HTTPS staging custom domain, including deactivation/recovery, is required before M2-01 completion. Cloudflare is a candidate, not a selected provider.
