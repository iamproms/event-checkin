# Event Check-in Platform PRD Review

**Status:** Step 1 review with product-owner decisions recorded; remaining details are open  
**Source reviewed:** `docs/Event_Checkin_Platform_PRD.pdf`, Version 1.0, September 17, 2026  
**Scope:** Requirements analysis and decision log only. No features or architecture are approved by this review.

## Executive assessment

The PRD establishes a coherent product direction: a white-label SaaS platform for event registration, QR-based check-in, offline gate operations, and attendance reporting. It identifies the main personas, the primary workflows, and a useful initial scale target of 10,000–15,000+ participants per event.

It is not yet implementation-ready. Several choices that materially affect security, data modeling, rollout, and scanner correctness are either contradictory or unspecified. In particular, the rollout plan conflicts with the requirement to design multi-tenancy into v1; offline first-timestamp-wins cannot be trusted without a time and conflict policy; and the promised privacy boundary for gate staff conflicts with the participant details shown in scanner and dashboard flows.

This review separates what the original PRD states from subsequent product-owner decisions and recommendations. The approved changes below supersede conflicting PRD wording for the launch design. Remaining details must stay visible as assumptions in the technical design.

## Product-owner decisions after review

The product owner answered the eight approval questions after the initial review. “Launch” below means the first production release.

| Decision | Approved direction | Effect on the original PRD |
|---|---|---|
| D-01 | Launch supports multiple tenants, tenant branding, and custom domains. | Supersedes Phase 1’s “single-tenant core”; F-01 and N-03 are launch scope. |
| D-02 | Check-in requires online connectivity for now. | Defers offline validation, offline scan queues, offline sync, first-timestamp-wins, and pending-sync counts (F-06, F-08, offline portion of F-09, N-04). A failed connection cannot produce a successful check-in. |
| D-03 | A QR code alone is sufficient evidence at entry. | The QR remains a bearer credential; a forwarded code can be used by the first presenter. Staff do not need participant identity details to accept entry. |
| D-04 | Staff may use personal phones or organizer-provided devices. | Device ownership is flexible. The installable web scanner remains the proposed client approach, pending supported-browser decisions. |
| D-05 | Launch supports one check-in session per event. | Multi-day/session, re-entry, and ticket-class behavior are outside the approved launch scope unless separately specified. |
| D-06 | Tenant admins can export and delete participant data without platform-admin support. Personal data is automatically removed 90 days after the event; anonymized attendance statistics and analytics remain. | Requires an explicit data lifecycle, export/deletion permissions, and anonymous aggregates. Event-relative deletion timing still needs a precise anchor. |
| D-07 | SMS, WhatsApp, billing, fully custom domains, and PDF reports are required at launch. | Pulls these features into launch scope; provider, pricing, billing workflow, and message-consent details remain open. This interprets the product owner's “Yes” as applying to all items in question 7. |
| D-08 | The technical design should propose measurable service targets. | Targets were proposed in Step 2 and subsequently approved by D-12. |
| D-09 | Backend stack is FastAPI. | Replaces the Step 2 NestJS proposal; the API and worker design will use Python. |
| D-10 | Attendees may not share email addresses or phone numbers within an event. | Both are required and individually unique per event for self-registration and bulk import. Exact normalization and correction flows are technical proposals. |
| D-11 | Tenant admins may delete individual participant data and whole-event participant data; the 90-day timer starts at event end. | Approves the proposed retention anchor and self-service deletion scope. Anonymous event statistics remain. |
| D-12 | The measurable service targets proposed in Step 2 are approved. | Section 12 of `TECHNICAL_DESIGN.md` becomes the launch sizing and service objective baseline. |
| D-13 | Billing uses Paystack subscriptions in NGN. | Confirms the launch payment provider, recurring model, and currency. Plan prices, billing interval, trials, add-on charging, taxes, and suspension rules remain open. |

### Consequences needing attention

- The original offline-first promise is deferred by D-02. Venue connectivity and a backup network become event-day dependencies; the scanner must clearly refuse check-in when the server cannot confirm it.
- “Non-transferable” in Section 5.3 cannot be guaranteed with QR-only entry (D-03). The attainable property is one successful redemption per ticket while online.
- The original scanner screen’s participant name and duplicate location/time are not needed for D-03. The launch scanner can show a minimal success/duplicate/invalid result; whether staff may see any identifying details remains open.
- D-06 preserves anonymous aggregates after the 90-day purge. Participant-level reports and old exports cannot remain available after their underlying personal data is deleted.
- D-10 rules out household/group registration under one contact address or number in launch scope. Every attendee needs their own email and phone; duplicate contact values are validation errors, not an automatic merge.

## Product intent and confirmed scope

The following are treated as confirmed because they appear as direct goals, features, or functional requirements in the PRD:

- **Reusable white-label SaaS:** multiple client tenants, tenant branding, custom domains, and multiple events per tenant (Sections 2, 3, 5.1, 6).
- **Registration:** event-specific public self-registration and admin bulk import from Excel/CSV, including validation and error reporting (Sections 5.2, 6).
- **Participant tickets:** unique, non-sequential QR credentials delivered by email, with an admin resend path (Sections 5.3, 6).
- **Gate operation:** installable mobile web scanner, gate-staff logins, multiple simultaneous gates, and offline scanning with later synchronization (Sections 2, 5.4, 6).
- **Attendance state and visibility:** check-in and scan-attempt records, a dashboard with synced and pending information, aggregate counts, and gate breakdowns (Sections 5.5, 6).
- **Messaging:** templated and segmented email as the primary channel; SMS and WhatsApp are optional paid channels, with Nigeria-capable delivery (Sections 3, 5.6, 6).
- **Reporting:** event-scoped attendance, no-show, gate/time, and flagged-scan reports, exportable as CSV and PDF (Sections 3, 5.7, 6).
- **Platform operations:** a super-admin capability for client accounts, billing, domains, and platform settings (Sections 4, 5.1, 11.7).
- **Initial scale and quality goals:** 10,000–15,000+ participants per event, near-one-second scan validation, extended offline operation, high availability during event opening, and NDPA-conscious handling (Sections 3, 7).

These are confirmed goals and workflows, not enough detail to settle every implementation behavior. For example, “near-instant” and “extended periods” need measurable acceptance thresholds.

## Functional requirements inventory

| ID | Requirement in the PRD | Source | Specification status |
|---|---|---|---|
| F-01 | Support multiple isolated client tenants, each with a custom domain. | 6.1; 5.1 | Isolation strength, domain lifecycle, and verification are open. |
| F-02 | Support multiple independent events over time for each tenant. | 6.2 | Event lifecycle and archival/retention rules are open. |
| F-03 | Generate one unique, signed, non-sequential QR credential per registrant. | 5.3; 6.3 | Token contents, cryptographic scheme, expiry, rotation, and revocation are open. |
| F-04 | Accept self-registration and bulk Excel/CSV upload, including 10,000+ rows and row-level validation/deduplication feedback. | 5.2; 6.4 | Identity/deduplication key, import limits, and correction workflow are open. |
| F-05 | Deliver QR credentials by email and allow admin resend. | 5.3; 6.5 | Delivery timing, bounce handling, resend limits, and ticket replacement behavior are open. |
| F-06 | Validate QR credentials offline from a pre-downloaded, encrypted event token set. | 5.4; 6.6 | Cache contents, authorization, expiration, refresh, and device loss handling are open. |
| F-07 | Provide scan-only gate-staff access scoped to an event and optionally a named gate. | 4; 5.4; 6.7 | Provisioning, authentication, session duration, gate reassignment, and revocation are open. |
| F-08 | Resolve duplicate scans made offline at multiple gates using “first-timestamp-wins.” | 5.4; 6.8 | Clock trust, timestamp authority, tie handling, and already-issued offline feedback are open. |
| F-09 | Show live check-ins and distinguish synced from pending-sync counts. | 5.5; 6.9 | “Live” latency and device heartbeat/staleness semantics are open. |
| F-10 | Send segmented bulk email; offer optional SMS/WhatsApp via a Nigeria-capable provider. | 5.6; 6.10 | Segment definition, consent, opt-out, provider, pricing, and delivery status semantics are open. |
| F-11 | Produce attendance, no-show, gate/time, and flagged-scan reports in CSV and PDF. | 5.7; 6.11 | Definitions, access control, retention, and export limits are open. |
| F-12 | Log every scan attempt with timestamp, gate/device ID, and result. | 6.12 | Retention, audit immutability, and treatment of unknown/forged tokens are open. |
| F-13 | Allow super-admin tenant setup and manage billing, domains, and platform-wide settings. | 4; 5.1; 11.7 | Billing model, plans, tenant lifecycle, and support access are open. |
| F-14 | Provide event setup, registration forms, participant management, messaging, dashboards, and report access through client admin screens. | 5; 11 | Detailed admin workflows, permissions, and acceptance criteria are open. |

## Non-functional requirements inventory

| ID | Requirement in the PRD | Source | Missing measure or operational detail |
|---|---|---|---|
| N-01 | Signed/encrypted QR tokens, strict tenant isolation, and NDPA-compliant participant data and consent handling. | 7 | Threat model, encryption boundaries, retention, data-subject handling, breach response, and consent evidence are undefined. “Signed/encrypted” needs a precise security property. |
| N-02 | 10,000–15,000+ registrants per event; online/offline scan validation near 1 second. | 3; 7 | No throughput, concurrency, latency percentile, import duration, or supported hardware/browser profile. |
| N-03 | Multi-tenant, multi-event structure from v1. | 7 | Conflicts with the phased rollout’s single-tenant Phase 1. |
| N-04 | Check-in must function with zero venue connectivity for extended periods. | 7 | Maximum offline duration, cache size, stale-data policy, and required pre-event preparation are unspecified. |
| N-05 | Near-zero-training scanner that works on personal phones of varying quality. | 7 | Supported devices, browsers, camera capabilities, accessibility targets, and minimum scanner performance need definition. |
| N-06 | High availability during live event windows, especially the first gate-opening hour. | 7 | Availability target, event-window definition, recovery objectives, operational support, and load profile are unspecified. |
| N-07 | Exportable reports and historical retention across repeated/multiple events. | 3; 5.7 | Retention duration, deletion behavior, storage location, and export completion time are unspecified. |
| N-08 | White-label branded environments and custom domains. | 3; 5.1 | Domain onboarding, TLS issuance/renewal, email sender verification, branding limits, and fallback behavior are unspecified. |

## Ambiguities, gaps, and conflicts

### Product behavior

1. **Rollout conflicts with the v1 architecture goal.** The NFR says multi-tenant and multi-event must be designed into v1, while Phase 1 explicitly says “Single-tenant core” and defers the white-label layer to Phase 2. Clarify whether tenancy is present from the first production release and whether custom domains/branding are also MVP scope.
2. **“Participant” identity and duplicate registration are undefined.** The PRD asks for deduplication but does not state whether email, phone, a combination, or an event-specific identifier defines a duplicate. It does not define updates, shared family/team email addresses, walk-ins, cancellations, or re-registration.
3. **Event lifecycle is too coarse.** Draft/live/closed are named, but registration opening/closing, event time zones, multiple days/sessions, ticket cancellation, attendee eligibility changes, check-in reopening, and event archival are not specified.
4. **No operating assumptions for setup day.** Offline scanning depends on devices obtaining authorized event data before connectivity is lost. The PRD does not define who prepares devices, when a token set is current, or how staff confirm readiness.
5. **“Live” and “pending-sync” have no semantics.** Define the dashboard latency target and how the UI detects a disconnected, stale, or never-synced device. Without device heartbeats, pending-scan totals cannot be authoritative while offline.
6. **Messaging consent and channel behavior are incomplete.** The NFR mentions consent, but there is no consent capture, proof, opt-out, suppression, sender identity, template approval, or distinction between transactional ticket mail and marketing/event updates. Paid add-on packaging also lacks scope and pricing rules.
7. **Participant-facing delivery flow is underspecified.** The PRD says the QR is emailed and the registration confirmation directs the participant to check email. It does not define email changes, delivery failure recovery, ticket replacement, language/localization, or whether a participant can retrieve a ticket without admin intervention.
8. **Reporting definitions are open.** “Checked-in,” “no-show,” “duplicate,” “invalid,” “flagged,” and “by gate/time” need consistent definitions, especially when a scan’s initial offline result is later superseded.

### Security, privacy, and trust boundaries

9. **“Signed/encrypted QR” combines different properties.** A digital signature/MAC provides integrity/authenticity; encryption hides contents. The PRD does not say whether QR payloads contain personal data, whether they must be confidential, or how keys are protected and rotated.
10. **Non-transferability is not achieved by a QR code alone.** A bearer QR can be copied or forwarded. Single-use detection can reject later scans once the system has a consistent record, but it cannot prove that the first presenter is the intended person. Decide whether the product accepts this limitation or requires an identity check (for example, a staff-visible name or photo), and what data that check entails.
11. **Offline first-timestamp-wins trusts device clocks.** Offline devices can have inaccurate, changed, or manipulated clocks. The server cannot infer true event order from an untrusted local timestamp. The PRD does not say whether first observed locally, first received by server, gate priority, or another policy wins, nor how to treat ties.
12. **Offline duplicate feedback cannot be final across disconnected gates.** A scanner with no connectivity cannot know that another disconnected gate has already accepted the same credential. It may show a provisional success that later loses reconciliation. The product must set acceptable duplicate-entry risk and define how staff/admins are informed after sync.
13. **Offline cache and device compromise are unaddressed.** A token set must be available on personal phones, but the PRD does not define encryption at rest, device binding, local data minimization, screen-lock expectations, logout/wipe behavior, cache expiry, or whether names are cached. Browser storage encryption is not an automatic substitute for a device security model.
14. **Gate-staff data scope conflicts with the UI.** The role says staff have no participant data beyond confirming check-in, yet the scanner success state displays a participant name and duplicate feedback shows where/when first used. Choose the minimum data needed at the gate and explicitly authorize it.
15. **Account security and tenant boundaries are not specified.** Password hashes appear in the data model, but MFA, invitation/reset flows, session revocation, role administration, audit logs, API authorization, tenant resolution from custom domains, and platform-admin access to tenant data are not covered.
16. **NDPA compliance is asserted without requirements.** Define controller/processor responsibilities, consent and lawful-basis capture, retention/deletion, access/export requests, breach handling, vendor assessment, and cross-border processing. These choices affect product scope and provider selection.

### Architecture and operational risks

17. **Tenant ID scoping alone can be fragile.** The PRD proposes shared-database tenant scoping but does not specify database constraints, row-level defenses, tenant context propagation, background job scoping, or tests against cross-tenant access. A missed filter could expose another client’s data.
18. **Bulk-import scale and email bursts need capacity assumptions.** “10,000+ rows” and batch sending are stated, but there are no concurrent imports, event peak patterns, provider rate limits, retry behavior, or partial-failure UX.
19. **Custom domains create provisioning and routing dependencies.** Domain ownership validation, DNS propagation, TLS, tenant lookup, sender-domain authentication, conflicting domain claims, and deprovisioning need a defined lifecycle.
20. **Browser/PWA offline and camera support vary.** “In-app camera” should be understood as camera access in the web app; browser permissions and device support vary. The PRD needs supported platform/browser minimums, installation assumptions, and a plan for camera denial or unsupported devices.
21. **No service objectives or incident operations are set.** Monitoring, alert ownership, backups/restore, disaster recovery, event-day support, maintenance windows, and incident communications are absent despite the high-availability goal.
22. **Billing is named but not specified.** Tenant plan, usage metering, limits, payment collection, invoicing, trial/suspension, and add-on billing are product decisions. They may be deferred, but “manage billing” should not silently imply a full billing system in the first release.

## Confirmed requirements versus recommendations

### Confirmed by the PRD

The requirements listed under [Product intent and confirmed scope](#product-intent-and-confirmed-scope), plus F-01–F-14 and N-01–N-08, are grounded in explicit PRD statements. The statements remain subject to the conflicting scope and unresolved behavior identified above.

### Recommendations for approval (not requirements yet)

- Resolve the v1 scope conflict by deciding whether the MVP is multi-tenant from its first production deployment. If it is, build and test tenant boundaries from the start, even if paid white-label features roll out later.
- Choose an explicit offline duplicate policy and label offline accepts as provisional where the device cannot establish global uniqueness. Do not treat client clock time as authoritative without an approved trust mechanism.
- Minimize cached personal data; define the offline bundle contents, device/session binding, expiry, revocation behavior, and staff-visible information before choosing token and storage designs.
- Separate ticket authenticity from confidentiality in the QR threat model. Prefer opaque, high-entropy ticket identifiers with server-side state where feasible; approve any offline-verification mechanism based on key exposure and revocation trade-offs.
- Define measurable service targets: peak scan/import/send load, scan latency percentile, offline duration/cache size, dashboard freshness, availability during an event, and recovery objectives.
- Define explicit retention and deletion rules for participant records, scan/audit data, delivery logs, exports, and offline device data.
- Treat billing, SMS/WhatsApp, fully custom domains, PDF reports, and advanced analytics as separately scoped capabilities unless they are required at launch.
- Establish supported mobile browsers/devices and a field readiness checklist so the scanner’s offline and camera assumptions can be tested before events.

These were recommendations at the initial review. D-01 through D-08 record the product-owner decisions that now govern launch scope; any recommendation not covered by those decisions remains unapproved.

## Original approval questions and remaining details

The questions below prompted D-01 through D-08 above. Their broader technical details are still open and will be marked as proposals in Step 2.

1. **MVP tenancy:** Should the first production release support multiple tenants and tenant-scoped events, as the NFR states, or may Phase 1 be single-tenant with a migration later? Are custom domains and branding required in that first release?
2. **Offline duplicate outcome:** What should happen when the same ticket is scanned offline at multiple gates? Options include accepting provisional entry at each gate then resolving centrally; defining a designated gate/device priority; or requiring online connectivity for strict single-use enforcement. What maximum duplicate-entry risk is acceptable?
3. **Identity evidence at entry:** Is a QR ticket alone sufficient, or must staff see/check participant name, photo, or another identifier? Which minimum participant fields may be stored offline and shown to gate staff?
4. **Scanner operating model:** Are personal phones and installable PWA mandatory, or are managed/owned devices or a native app acceptable? What minimum offline duration and device/browser support should be guaranteed?
5. **Event scope:** Is this single-session check-in, or must v1 handle multi-day events, sessions, re-entry, ticket classes, guest groups, cancellations, and on-site registration?
6. **Privacy and retention:** What retention period and deletion expectations apply to participant details, scan attempts, message logs, and exports? Should tenant admins be able to delete/export data without platform support?
7. **Launch commercial scope:** Are SMS/WhatsApp, billing, fully custom domains, and PDF reports required at launch, or can they be phased after core check-in?
8. **Service targets:** Can you approve measurable targets for peak event traffic, online scan latency, dashboard freshness, offline duration, and event-window availability? If not, may the technical design propose targets for approval?

## Readiness and next step

The PRD and D-01 through D-13 now establish the launch boundary, core service targets, and Paystack subscription direction. FastAPI is the approved backend framework. Plan terms, messaging consent, scanner feedback, QR confidentiality, and several operating policies remain proposals for review.

No implementation has been started.
