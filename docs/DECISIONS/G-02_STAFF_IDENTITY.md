# G-02 — Staff Identity, Authentication and Session Policy

**Project:** Event Check-in Platform
**Decision ID:** G-02
**Status:** APPROVED
**Date:** 2026-10-23
**Implementation milestone:** M1-03
**Authority:** Product owner approval

## 1. Decision

The Event Check-in Platform will implement first-party staff authentication using Argon2id password hashing and opaque, server-managed sessions.

Authentication, session management, and authorization must be implemented server-side. The platform will not use an external OIDC provider for M1-03.

This decision resolves the G-02 identity-policy dependency identified in the implementation plan.

## 2. Authentication

- Staff authenticate using their verified email address and password.
- Passwords are hashed using Argon2id with unique salts and appropriate cost parameters.
- Plaintext passwords must never be stored or logged.
- Sessions use cryptographically secure, unpredictable opaque tokens.
- Only a cryptographic hash of each session token is stored server-side.
- Session tokens are transported through Secure, HttpOnly cookies with an appropriate SameSite policy.
- Session identifiers are rotated following authentication and privilege-sensitive transitions.
- Logout, account suspension, and administrative revocation invalidate affected sessions server-side.
- State-changing requests require CSRF protection.

## 3. Multi-Factor Authentication

MFA is mandatory for privileged staff:

- Platform administrators.
- Tenant owners and administrators.
- Event organizers and managers.
- Gate supervisors.
- Support staff with privileged access.

MFA is optional for restricted gate scanners.

Approved MFA mechanisms:

- Time-based one-time passwords (TOTP) using authenticator applications.
- Single-use recovery codes.

Email and SMS are not approved as standalone substitutes for required MFA.

Staff who have not completed mandatory MFA enrollment must not receive privileged access.

MFA enforcement is based on effective permissions, not merely a displayed role name.

## 4. Session Lifetime

| Staff category | Idle timeout | Absolute lifetime |
|---|---|---|
| Platform administrators | 15 minutes | 8 hours |
| Tenant owners and administrators | 15 minutes | 8 hours |
| Organizers and managers | 30 minutes | 8 hours |
| Gate supervisors | 30 minutes | 8 hours |
| Restricted gate scanners | 30 minutes | 12 hours |
| Privileged support staff | 15 minutes | 8 hours |

Sessions expire when either their idle timeout or absolute lifetime is reached.

Activity may extend the idle deadline but must never extend the absolute deadline.

Privilege changes require fresh authorization and appropriate session rotation or revocation.

## 5. Staff Invitations

Staff onboarding is invitation-only.

- Authorized administrators issue invitations to specific email addresses.
- Invitations are single-use and expire after 48 hours.
- Invitations contain cryptographically secure, unpredictable tokens.
- Only invitation-token hashes are stored server-side.
- The invited person verifies the invitation, establishes credentials, and enrolls in MFA when required.
- Tenant membership must not become active until invitation acceptance and all required enrollment steps are complete.
- Invitations must not grant privileges beyond those the inviting administrator is authorized to delegate.
- Public self-registration for staff is not part of M1-03.

## 6. Password and Account Recovery

- Minimum password length: 12 characters.
- Support passwords of at least 128 characters.
- No arbitrary uppercase, numeric, or symbol composition requirements.
- Reject known compromised passwords.
- Apply rate limiting to authentication and recovery endpoints.
- Password-reset links are single-use and expire after 30 minutes.
- Password resets invalidate existing authenticated sessions, except any explicitly re-established through the new authentication flow.
- MFA recovery uses single-use recovery codes.
- Loss of all MFA recovery methods requires documented administrative identity verification.
- Email access alone must not bypass mandatory MFA.
- Recovery responses must not disclose whether an account exists.

## 7. Tenant Authorization

Authentication establishes identity; tenant membership establishes authorization.

- Verify the authenticated user's active tenant membership on the server.
- Enforce effective permissions for every protected operation.
- A hostname, request header, URL parameter, or client-supplied tenant ID cannot establish authorization.
- Tenant switching requires verification of membership in the destination tenant.
- Set PostgreSQL transaction-scoped tenant context only after successful authorization.
- Preserve FORCE ROW LEVEL SECURITY and restricted runtime database roles.
- Deny access when membership, permissions, session validity, or tenant context cannot be verified.
- Revoked memberships and changed permissions must take effect without waiting for the session's natural expiration.

## 8. Security and Auditability

Record security-relevant events, including successful and failed authentication, MFA enrollment and recovery, invitation issuance and acceptance, session revocation, and permission changes.

Audit records must avoid passwords, raw session tokens, recovery tokens, TOTP secrets, and other sensitive credentials.

## 9. Implementation Constraints

M1-03 must:

- Build upon the merged M1-02 schema.
- Respect the approved API and domain contracts.
- Add only the migrations necessary for authentication, invitations, MFA, sessions, and authorization.
- Include PostgreSQL integration tests for tenant authorization and session isolation.
- Preserve existing database security controls.
- Avoid implementing later event-management, scanning, billing, or analytics milestones.

**Decision outcome:** APPROVED for implementation in M1-03.

## 10. Product-owner addendum (2026-10-23)

- Compromised-password screening uses an offline, maintained, versioned corpus through a configurable screening interface. Credential creation and reset fail closed when an approved dataset is absent. No dataset is approved by this record merely by naming the approach.
- Invitation and reset delivery uses a provider-independent adapter with local development support. Production email activation waits for a separately approved provider. Tokens are never logged.
- Initial effective permissions are least-privilege: tenant owners/admins manage tenant settings, staff, invitations, events, gates, reporting, attendee exports, and billing in their tenant; organizers/managers manage events and gates, check in, report, and export within assigned events; gate supervisors operate/configure assigned gates, check in, and see assigned-gate operational reporting; gate scanners check in at assigned gates only, with no identity display, export, reporting, staff, or billing access. Platform administrators handle separately authorized platform operations without implicit tenant-data access. Support requires explicit time-limited auditable grants for specific operations and has no default tenant-data access. Effective permissions, not role names alone, drive MFA.

This addendum does not approve a production mail vendor or a particular compromised-password dataset. Those are activation prerequisites, not reasons to bypass checks.

**M1-03 platform/support scope clarification:** Introduce the grant schema only. Do not expose platform/support sign-in or operations until the dedicated host and operation contracts are approved. The absence of those routes grants no tenant-data access.

**Initial owner clarification:** Trusted tenant provisioning in M2 will create the first-owner invitation path. M1-03 does not add public self-registration or an operator bootstrap endpoint.
