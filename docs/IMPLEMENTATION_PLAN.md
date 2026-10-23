# Event Check-in Platform — Implementation Plan

**Status:** Step 4 planning proposal; no feature implementation has begun.  
**Inputs:** [PRD review](PRD_REVIEW.md), [technical design](TECHNICAL_DESIGN.md), [database design](DATABASE_DESIGN.md), and the [Quiet Precision design-system study](DESIGN_SYSTEM.md).  
**Decision baseline:** D-01–D-13 in the PRD review. Quiet Precision is the working visual foundation for planning; exact aesthetic tokens remain subject to visual approval.  
**Planning unit:** Each task is independently reviewable and should be small enough for one pull request or a clearly identified short series of dependent pull requests. No dates or staffing estimates are asserted without team capacity and vendor lead-time information.

## 1. Delivery rules and scope

The launch delivers a multi-tenant SaaS with branding and custom domains, single-session events, required unique attendee email and phone per event, QR-only entry evidence, **online-only** check-in, staff use on personal or organizer devices, live confirmed attendance, bulk import, ticket email, email/SMS/WhatsApp campaigns, CSV/PDF reports, self-service export/deletion, 90-day participant-data removal, and Paystack subscriptions in NGN. FastAPI is the approved backend (D-09). Measurable targets were requested in D-08 and approved in D-12; Section 12 of the technical design is the performance and recovery baseline.

**Deferred by D-02:** offline QR validation, local credential manifests, queued scans, synchronization, first-timestamp-wins, and pending-sync dashboard counts (F-06, F-08, N-04 and the offline part of F-09). They have no launch tasks or hidden acceptance criteria. A later offline release requires a separate PRD, threat model, policy, and plan.

The milestone order expresses the **critical dependency path**, not a prohibition on parallel work. Frontend work may proceed alongside the corresponding API work once its contracts and design foundation are approved. Provider integrations can be built behind adapters, but production activation cannot be marked done before commercial, legal, and vendor decisions are recorded.

### Shared definition of done for every implementation task

A task closes only when its acceptance criteria are demonstrated; API/data contracts and migration notes are current; tenant, role, privacy, and failure paths are reviewed where relevant; its specified automated/manual tests are in the delivery pipeline; observability and support notes exist for operational behavior; and a reviewer can reproduce the evidence in a non-production environment. A task with an unresolved decision is **blocked for completion**, even if preparatory code exists. Test requirements below describe future implementation work; no tests or application code are added by this planning document.

## 2. Decisions and stage gates

| Gate | Decision needed | Blocks completion of | Recorded output |
|---|---|---|---|
| G-01 Product contracts | Registration correction/replacement and on-site registration; event cancellation/reopening; metric definitions for deletion and no-show | M2-03, M3-01, M3-03, M4-04, M5-02 | Signed product-state and metric glossary; API examples |
| G-02 Identity and gate policy | Staff authentication, MFA, session values, and initial least-privilege permissions approved in [G-02](DECISIONS/G-02_STAFF_IDENTITY.md); browser/device support, scanner label, and connectivity escalation remain for gate operations | M4-01, M4-03, M6-03; M1-03 production activation still needs approved password corpus and email provider | Approved decision record and remaining gate-operation policy |
| G-03 QR policy | Signed non-PII QR with encrypted stored resend copy and TLS, or another explicitly approved confidentiality model | M3-02, M4-02 | QR threat model and key-management record |
| G-04 Communications | Transactional/promotional purposes, consent/opt-out language, sender verification, SMS/WhatsApp provider and approved templates | M3-02, M5-01/04/05 | Messaging policy and vendor onboarding record |
| G-05 Commercial | Paystack plan prices, interval, trials, included usage, add-ons, tax, renewal/nonpayment policy | M2-02, M5-04/05 where channel charges apply, M6-03 | Plan catalog and entitlement state table |
| G-06 Privacy and vendors | Region/cross-border processing, export artifact lifetime, deletion execution timing, suppression-retention basis, aggregate privacy threshold, backup expiry | M1-01, M2-01, M5-02/03/04/05, M6-02 | Data-lifecycle and vendor decision record |
| G-07 Visual foundation | Final font, tokens, supported theme behavior, brand override range, navigation treatment, density/radius defaults after browser/device review | M1-05 and all production UI acceptance | Approved design-system revision |

**Working assumptions pending approval:** never interrupt a live scan because billing status changes; scanner shows result without attendee identity; admin-requested deletion is irreversible once executed; public duplicate-registration responses avoid account enumeration. These are proposals already identified in the design documents, not new approvals. A task may prepare interfaces and adapters while its gate remains open, but cannot claim production-ready behavior that depends on it.

## 3. Milestone map

| Milestone | Outcome and exit evidence | Main dependencies |
|---|---|---|
| M0 — Contracts and decisions | Decision record, state glossary, reviewed API/error/event contracts | D-01–D-13 and gates G-01–G-07 |
| M1 — Secure foundation | Deployable service skeleton, tenant-safe schema/RLS, auth, jobs/storage, approved UI primitives | M0 contract baseline; G-02/G-06/G-07 for final policies |
| M2 — Tenant and event setup | Provisioned tenants, verified domains/branding, NGN billing, event/form configuration | M1 isolation/auth/jobs; G-05 |
| M3 — Registration and tickets | Public/self and bulk registration, unique contacts, QR issue/reissue and delivery, participant administration | M2 events; M1 jobs; G-01/G-03/G-04 |
| M4 — Online gate and live operations | Atomic one-use redemption, assigned staff scanner, confirmed live metrics | M3 tickets; M1 auth/RLS; G-02/G-03 |
| M5 — Messaging, reports and privacy | Email/SMS/WhatsApp sends, CSV/PDF jobs, admin export/deletion, 90-day purge and anonymous history | M3 participant data; M4 scan data; G-04/G-05/G-06 |
| M6 — Release hardening | Measured targets, incident readiness, security/accessibility review, pilot and release evidence | All launch capabilities and open gates resolved |

## 4. Tasks

### M0 — Contracts and decisions

#### M0-01 — Close product and policy decisions
- **Objective and scope:** Resolve G-01–G-06 with named owners; record accepted defaults and rejected alternatives in a versioned decision register. Include billing, consent, browser/device, region/vendor, QR, deletion and metrics decisions.
- **Dependencies:** Existing PRD review and design proposals; product, operations, security/privacy, and vendor input.
- **Acceptance criteria:** Every gate has an explicit decision, owner, date and effect on scope/contracts; unresolved items are tagged to blocked tasks; no decision contradicts D-01–D-13.
- **Testing requirements:** Scenario walkthroughs for duplicate contact, copied QR, network loss, deletion before/after event, failed payment during live scan, and low-count aggregate reports.
- **Definition of done:** Decision register is approved and linked from relevant specifications; changed requirements are traced to affected task IDs.

#### M0-02 — Freeze launch domain, API and metric contracts
- **Objective and scope:** Define event/ticket/check-in state diagrams, error codes, idempotency behavior, report metric definitions, API request/response examples, provider callback contracts, and data retention ownership. Confirm single-session semantics.
- **Dependencies:** M0-01 for policy-dependent states; technical and database designs.
- **Acceptance criteria:** Contract examples cover accepted, duplicate, invalid/revoked, event closed and cannot-confirm outcomes; both unique-contact errors; job progress/failure; payment and domain states; no offline success or pending-sync state.
- **Testing requirements:** Contract review against PRD F-01–F-14 and N-01–N-08; schema/example validation and state-transition table review.
- **Definition of done:** Versioned contracts and glossary are signed off for backend/frontend work; open API questions are tracked rather than embedded as assumptions.

#### M0-03 — Approve the visual foundation for production UI
- **Objective and scope:** Use the Quiet Precision laboratory to choose and document actual font packaging, light/dark tokens, semantic colors, density/radius, navigation treatment, icon and motion rules, and tenant branding bounds. Keep application layouts as separate later design work.
- **Dependencies:** Current `DESIGN_SYSTEM.md`, real browser/device visual review, G-07.
- **Acceptance criteria:** One primary sans family and token set are selected; Inter/Geist rendering and glyph fallback are inspected; light/dark, 320px/200% zoom, focus and status distinction are reviewed; white-label overrides have contrast rules.
- **Testing requirements:** Browser screenshots at representative widths/themes, keyboard and screen-reader spot checks, contrast checks, and sample Nigerian names/₦/long strings.
- **Definition of done:** Product owner approves a versioned design-system revision. Until then, UI task completion uses the current foundation only as a working hypothesis.

### M1 — Secure foundation

#### M1-01 — Establish environments and delivery pipeline
- **Objective and scope:** Create the FastAPI/web/worker repository structure, local development setup, staging and production separation, infrastructure as code, secrets/configuration handling, database/Redis/object storage connections, CI checks and release migration workflow.
- **Dependencies:** M0-02 baseline; G-06 for production region/provider choice.
- **Acceptance criteria:** A minimal non-feature deployment can be built and promoted to staging; secrets are external; health/readiness distinguish API, database and worker state; migration rollback/forward policy is documented.
- **Testing requirements:** CI smoke checks, configuration validation, deployment and rollback rehearsal in staging, secret-leak and dependency/container scans.
- **Definition of done:** Team can deploy an empty service safely with repeatable environments and documented operator commands.

#### M1-02 — Implement tenant-safe PostgreSQL schema and migrations
- **Objective and scope:** Create core tenant, domain, identity, event, registration, ticket, scan, job, billing and aggregate tables as needed by first consumers; composite tenant/event foreign keys; uniqueness; `FORCE ROW LEVEL SECURITY`; separate runtime/platform roles; migration conventions.
- **Dependencies:** M0-02 contracts; M1-01 database environment.
- **Acceptance criteria:** Runtime role cannot bypass RLS; verified tenant context is set per transaction; unknown context fails closed; independent event-scoped unique email and phone constraints exist; same-tenant/event linkage is enforced by composite keys.
- **Testing requirements:** Migration up/down on empty and seeded databases; cross-tenant read/write attempts; reused pooled-connection context tests; constraint and query-plan checks at 30,000-registration scale.
- **Definition of done:** Reviewed migrations and RLS inventory cover every tenant-owned table; database design and migration notes match deployed schema.

#### M1-03 — Implement staff/admin identity and authorization
- **Objective and scope:** Invite-only accounts, login/recovery/MFA per G-02, secure host-only sessions, CSRF protection, tenant memberships, platform grants, event/gate assignments, revocation, and audited privileged actions.
- **Dependencies:** M1-02; approved G-02 identity policy and initial role matrix; provider activation and password corpus remain separate gates.
- **Acceptance criteria:** Every API action checks server-derived tenant, active membership, role and event/gate scope; platform admins have no implicit participant access; session revocation applies on the next request.
- **Testing requirements:** API role matrix, tenant/host/ID substitution attempts, CSRF/session fixation/revocation tests, invitation/recovery edge cases, MFA paths where required.
- **Definition of done:** Authorization middleware and domain checks are reusable, documented and exercised by a negative-access suite.

#### M1-04 — Build reliable jobs and private file primitives
- **Objective and scope:** Transactional outbox, Celery/Redis worker execution, job states, idempotent retry/backoff, dead-letter inspection, private upload/download objects, signed short-lived URLs and object lifecycle hooks.
- **Dependencies:** M1-01/02; M0-02 job contracts.
- **Acceptance criteria:** A committed command cannot lose its intended outbox event; duplicate dispatch/job execution does not duplicate effects; workers re-establish tenant context from validated job IDs; Redis outage does not prevent an otherwise healthy scan transaction.
- **Testing requirements:** Crash/restart and duplicate-delivery tests; tenant-swapped job IDs; object access/expiry checks; queue failure and recovery exercise.
- **Definition of done:** Reusable job and storage interfaces, dashboards and runbook are ready for imports, email, campaigns, exports and purge.

#### M1-05 — Build approved UI primitives and accessibility baseline
- **Objective and scope:** Implement selected typography/tokens, buttons, fields, status, navigation, dialog, progress and responsive primitives after G-07; use one shared component layer across public, admin and scanner clients.
- **Dependencies:** M0-03; M1-01 web build; M0-02 state vocabulary.
- **Acceptance criteria:** Components expose keyboard/focus/error/loading/disabled/selected states; semantic statuses never inherit tenant accent; compact mode preserves touch-critical target size; no screen-specific decorative variants are embedded in primitives.
- **Testing requirements:** Component visual snapshots in both themes and density modes, 320px/200% reflow, keyboard and screen-reader checks, contrast for every published theme and tenant override.
- **Definition of done:** Documented components and token package are reviewed against approved `DESIGN_SYSTEM.md` and ready for feature teams.

### M2 — Tenant and event setup

#### M2-01 — Provision tenants and custom domains
- **Objective and scope:** Platform tenant creation; verified hostname ownership, DNS/TLS state machine, fail-closed host routing, and domain activation/deactivation. Keep web and sender-domain verification distinct.
- **Dependencies:** M1-02/03/04; M0-02; production edge/vendor decision in G-06; M1-05 for UI.
- **Acceptance criteria:** Unknown/unverified host cannot route to tenant data; one active primary domain per tenant; failed TLS or ownership state is visible and recoverable; routing and activation are audited.
- **Testing requirements:** Hostname collision/claim, IDN/punycode normalization, DNS/TLS retry, cross-tenant host spoofing and deprovisioning tests.
- **Definition of done:** Provisioning and support runbook, domain state API/UI, audit events, and a verified staging custom domain are reviewable.

#### M2-02 — Integrate Paystack subscriptions in NGN
- **Objective and scope:** Plan catalog and entitlements, checkout/subscription lifecycle, usage metering, verified webhook reconciliation, billing settings and platform oversight. Keep payment state separate from live scan authority.
- **Dependencies:** M1-02/03/04; G-05 commercial terms; M2-01 tenant identity.
- **Acceptance criteria:** NGN plan/usage/payment states match approved catalog; webhooks are signature-checked and idempotent; no card data is stored; nonpayment behavior follows approved policy and does not silently interrupt an active event.
- **Testing requirements:** Paystack sandbox contract tests, duplicate/out-of-order/forged webhook tests, renewal/failure/cancellation/reconciliation scenarios, once-only usage accounting.
- **Definition of done:** Finance/product approve billing state table and invoices/receipts responsibility; operator reconciliation procedure exists.

#### M2-03 — Configure events, forms and gates
- **Objective and scope:** Tenant-admin event creation/edit/publish/close, event time zone and one check-in window, versioned form schema, gate definitions, staff assignment hooks and event readiness state.
- **Dependencies:** M1-02/03/05; M2-01; G-01 event lifecycle decisions.
- **Acceptance criteria:** Event transitions are explicit and audited; `ends_at > starts_at`; form version is frozen with each registration; gate assignment cannot cross event/tenant; changing event end time recomputes purge due date under approved policy.
- **Testing requirements:** State transition, time-zone/DST, invalid form schema, role/tenant scope, publish/close/reopen policy and purge-date tests.
- **Definition of done:** Admin can configure a staging event and gates through reviewed API/UI with documented state semantics.

#### M2-04 — Publish tenant branding safely
- **Objective and scope:** Tenant logo/name, accent and sender display-name settings; asset validation/storage, light/dark contrast validation, preview and publish workflow. Sender-domain verification remains a separate messaging concern.
- **Dependencies:** M2-01 tenant identity; M1-04 storage; M1-05 UI primitives; G-07 brand bounds.
- **Acceptance criteria:** Tenant admins can publish permitted branding; invalid or low-contrast themes fail with actionable feedback; semantic success/warning/error colors stay platform-controlled; logo failure has a readable fallback.
- **Testing requirements:** Malformed/oversized SVG and image cases, cross-tenant asset access, long tenant names, light/dark contrast, keyboard and 320px reflow.
- **Definition of done:** Staging tenant can preview and publish branding across the documented surfaces with audit history and a safe rollback.

### M3 — Registration and tickets

#### M3-01 — Register attendees safely
- **Objective and scope:** Public registration on verified tenant domain with required name/email/phone, configurable fields, E.164 phone normalization, event-scoped independent uniqueness, consent evidence, privacy notice and safe public errors.
- **Dependencies:** M2-01/03/04; M1-02/03/05; G-01 correction policy and G-04 consent language.
- **Acceptance criteria:** Shared email or shared phone is rejected even when the other value differs; no automatic merge; public responses do not enumerate existing contacts; accepted registration creates exactly one active registration intent and delivery event.
- **Testing requirements:** Boundary/property tests for normalization and concurrency; duplicate email/phone separately; malicious custom fields; unauthenticated enumeration/rate-limit checks; keyboard/form accessibility.
- **Definition of done:** End-to-end registration flow and API contract pass, with audit/consent evidence and clear delivery-help state.

#### M3-02 — Issue, reissue, revoke and deliver tickets
- **Objective and scope:** Non-sequential QR credential generation, key rotation/versioning, encrypted stored resend copy, active-ticket uniqueness, resend/reissue/revoke commands, email template/PDF ticket if approved, transactional delivery worker and provider callbacks.
- **Dependencies:** M3-01; M2-04; M1-04; G-03 QR policy; G-04 transactional email/sender policy.
- **Acceptance criteria:** QR contains no personal fields; a revoked/reissued credential cannot redeem; resend keeps the same active credential; provider retries do not create new tickets or duplicate intentional sends; failed delivery has an admin recovery path.
- **Testing requirements:** Cryptographic format/tamper/key rotation tests, one-active-ticket constraint, duplicate job/callback tests, email rendering/QR scannability and PDF print checks.
- **Definition of done:** A staged attendee receives a usable ticket and admin can resend/reissue with audit evidence.

#### M3-03 — Import 15,000-row CSV/XLSX files
- **Objective and scope:** Private upload, parse/validate/preview, row-level error file, independent email and phone deduplication within file and event, explicit idempotent commit, progress and partial-failure reporting.
- **Dependencies:** M3-01 registration service; M1-04 jobs/storage; G-01 replacement policy.
- **Acceptance criteria:** No import silently overwrites an attendee; preview identifies invalid/duplicate rows without echoing full PII into logs; commit uses the same rules as self-registration; 15,000-row preview meets the approved ≤10-minute target in the specified test envelope.
- **Testing requirements:** Golden CSV/XLSX cases, malformed/bomb file limits, formula-injection checks, duplicate job/commit, row-count reconciliation, throughput and memory checks.
- **Definition of done:** Admin can preview, correct via documented flow, commit and retrieve concise errors/progress in staging.

#### M3-04 — Manage participants and ticket support
- **Objective and scope:** Tenant-admin participant list/search/filter, controlled detail access, ticket resend/reissue/revoke, and event-scoped correction actions allowed by G-01. Do not grant participant detail to gate staff.
- **Dependencies:** M3-01/02/03; M1-03/05; G-01.
- **Acceptance criteria:** Contact data is role-scoped; long names and addresses remain inspectable; actions have specific consequences and audit entries; participant detail disappears after deletion/purge.
- **Testing requirements:** Role and cross-tenant matrix, pagination/filter correctness, correction uniqueness, action idempotency, responsive/accessibility checks.
- **Definition of done:** Admin can resolve ordinary attendee support cases without platform-admin access.

### M4 — Online gate and live operations

#### M4-01 — Prepare gate staff and devices
- **Objective and scope:** Event/gate assignment, staff session entry, device registration/revocation, connectivity/readiness check and clear network/camera escalation copy for BYOD and organizer-owned devices.
- **Dependencies:** M1-03; M2-03; G-02 supported-browser/device and access policy.
- **Acceptance criteria:** Staff can scan only assigned event/gate; revoked/reassigned access fails on next request; device ownership does not change authorization; readiness distinguishes browser-online from server reachable.
- **Testing requirements:** Role/gate matrix, session expiry/revocation, device replacement, supported-phone camera/permission/connectivity field checklist.
- **Definition of done:** Event operator can prepare and verify a representative gate device without accessing participant details.

#### M4-02 — Redeem QR atomically online
- **Objective and scope:** FastAPI scan command verifies QR, tenant/event/staff/gate scope and active window; writes idempotency record, one check-in and every attempt; returns definitive result and server time. PostgreSQL is the decision authority.
- **Dependencies:** M3-02; M4-01; M1-02; G-03.
- **Acceptance criteria:** Concurrent gates produce exactly one accepted redemption; a retry with the same key returns the original result; new-key replay is duplicate; invalid/revoked/closed outcomes are logged safely; timeout never implies success; Redis outage does not block the authoritative transaction.
- **Testing requirements:** Database concurrency/race and retry tests, forged/cross-tenant QR tests, malformed/rate-limit cases, transaction rollback/fault injection, load at 25 requests/s with 50 scanners; API p95 ≤500ms and p99 ≤1s.
- **Definition of done:** Security and operations reviewers accept the single-use evidence, latency measurements, and safe logs.

#### M4-03 — Deliver the mobile online scanner
- **Objective and scope:** Installable PWA camera/decode, bounded scan loop, event/gate context, ready/reading/verifying/accepted/duplicate/invalid/closed/cannot-confirm/camera-unavailable states, idempotent retry and explicit rearm. Cache static shell only.
- **Dependencies:** M4-02; M4-01; M1-05; G-02 device matrix and feedback policy.
- **Acceptance criteria:** No local success/queue/token manifest exists; accepted state follows server commit only; transient network failure retains retry context; captured QR is not persisted, logged or placed in URLs; result is readable without color alone and without attendee identity by default.
- **Testing requirements:** Browser/device field tests on approved low-end and organizer devices, permission denial, offline/server timeout, duplicate frame, large text, landscape/portrait, screen-reader and one-handed target checks; supported-network UI p95 ≤2s.
- **Definition of done:** Gate operators can complete an observed staging rehearsal with minimal instruction and a documented fallback for connectivity loss.

#### M4-04 — Publish confirmed live attendance
- **Objective and scope:** Transactional summary updates, dashboard snapshot, SSE with polling fallback, gate/time counts, last update/connection state and a privacy-safe recent activity feed.
- **Dependencies:** M4-02; M1-04; M3-04; G-01 metric definitions.
- **Acceptance criteria:** Counts derive from committed records; no pending-sync count; disconnected admin view says when data was last confirmed; no participant details shown to unauthorized roles; p95 commit-to-view freshness ≤5s for connected clients.
- **Testing requirements:** Metric reconciliation, SSE disconnect/reconnect, Redis failure/polling fallback, concurrent scan update, authorization, latency and accessibility checks.
- **Definition of done:** Admin can distinguish zero, stale and unavailable data during a staged multi-gate rehearsal.

### M5 — Messaging, reports and privacy

#### M5-01 — Build campaign segmentation and email sending
- **Objective and scope:** Shared segment evaluation, consent/suppression filtering, audience preview, template ownership, explicit send confirmation, transactional/campaign email provider adapter, delivery history and retries.
- **Dependencies:** M3-01/04; M1-04; G-04 purposes, email provider and sender policy.
- **Acceptance criteria:** Only eligible recipients are sent; campaign snapshot is fixed at confirmation; queued/provider-accepted/delivered/failed/unknown are distinct; duplicate jobs/callbacks do not multiply sends.
- **Testing requirements:** Segment/consent/opt-out matrix, duplicate and out-of-order callbacks, provider failure/retry, rate limits and content escaping.
- **Definition of done:** Staging email campaigns through an approved sandbox/test provider reconcile to campaign history.

#### M5-02 — Produce CSV/PDF detail and aggregate reports
- **Objective and scope:** Attendance/no-show/gate/time/flagged-scan definitions, background export jobs, private signed downloads, formula-safe CSV, PDF rendering, detail expiry and retained anonymous aggregate views.
- **Dependencies:** M4-02/04; M1-04; G-01 metric definitions; G-06 aggregate threshold/export lifetime.
- **Acceptance criteria:** Report totals reconcile to committed check-ins and approved deletion rules; jobs expose progress/failure; participant-level files expire by purge; post-purge reports contain only approved anonymous cells; no public object URL.
- **Testing requirements:** Golden report datasets and PDF visual review, CSV injection, authorization and signed-URL expiry, low-cell suppression, large export and retry checks.
- **Definition of done:** Admin can generate CSV/PDF in staging and historical aggregates remain valid after a simulated purge.

#### M5-03 — Implement self-service privacy and 90-day purge
- **Objective and scope:** Tenant-admin person/event export and deletion, retention due/completion status, daily event-end-plus-90-day purge, anonymous aggregate finalization, object/file cleanup, backup/restore purge replay, minimal privacy audit.
- **Dependencies:** M3-01/02/03/04 participant and ticket paths; M4-02/04 scan and aggregate paths; M5-02 exports; M1-04 jobs/storage; G-06 deletion timing, suppression basis, aggregate threshold and backup policy.
- **Acceptance criteria:** Admin can export/delete without platform support; person and event deletion remove linked personal data; automatic purge completes within 24h after due time, retries safely, and leaves only approved anonymous stats; restored data is not served before due purges replay.
- **Testing requirements:** Table/object inventory and deletion assertions, interrupted/replayed purge, before/during/after-event count rules, backup restore rehearsal, cross-tenant authorization, 90-day clock boundary.
- **Definition of done:** Privacy reviewer signs off a repeatable data-lifecycle proof and operator runbook, including residual backup limits.

#### M5-04 — Add SMS campaign delivery
- **Objective and scope:** Add the approved Nigeria-capable SMS provider behind the messaging adapter, channel-specific consent/suppression, previewed cost/usage, callbacks, retries and sender readiness.
- **Dependencies:** M5-01 shared campaign rules; M2-02 if SMS is billed as an add-on; G-04 provider/consent and G-05 charging policy.
- **Acceptance criteria:** SMS cannot send without an eligible audience and explicit confirmation; provider-accepted is distinct from delivered; duplicate jobs/callbacks do not duplicate sends or charges.
- **Testing requirements:** Provider sandbox contract, opt-out and invalid-number cases, rate limiting, partial batch failures, callback replay and usage reconciliation.
- **Definition of done:** Approved test sends and usage records reconcile; operator instructions cover provider rejection and sender setup.

#### M5-05 — Add WhatsApp campaign delivery
- **Objective and scope:** Add the approved WhatsApp Business provider/template lifecycle, channel-specific consent, recipient preview, confirmed send, callbacks, retries and usage records.
- **Dependencies:** M5-01 shared campaign rules; M2-02 if WhatsApp is billed as an add-on; G-04 provider/template/consent and G-05 charging policy.
- **Acceptance criteria:** Unapproved templates or unverified sender cannot send; eligible recipients and cost are shown before confirmation; callback replay does not duplicate sends or charges; delivery state is honest.
- **Testing requirements:** Approved/unapproved template cases, consent/opt-out matrix, provider sandbox callbacks, failure/retry, out-of-order events and usage reconciliation.
- **Definition of done:** Staging WhatsApp campaign through the approved provider is reconciled and its onboarding/runbook is reviewable.

### M6 — Reliability and launch

#### M6-01 — Instrument and operate the service
- **Objective and scope:** OpenTelemetry traces, structured/redacted logs, metrics and alerts, deployment/rollback, backup/failover, event-day readiness and incident runbooks. Observe scan, database, queue, provider, domain/TLS, billing and purge health.
- **Dependencies:** M1-01/04 and concrete M2–M5 services.
- **Acceptance criteria:** On-call can locate a failed request/job without raw QR or contact data; event-window alerts page the right owner; critical scan path remains independent of Redis job availability; release migrations follow expand/migrate/contract.
- **Testing requirements:** Synthetic alerts, trace correlation, failover/restore and rollback drills, queue/provider outage exercises, redaction review.
- **Definition of done:** Operations accepts dashboards, alerts, escalation contacts, recovery playbooks and pre-event checklist.

#### M6-02 — Prove security, privacy and service objectives
- **Objective and scope:** Integrate threat-model findings, authorization/RLS verification, dependency/secrets review, performance/soak tests and recovery measurements against approved targets.
- **Dependencies:** All implemented launch paths; G-06 vendor/privacy policy; M6-01 telemetry.
- **Acceptance criteria:** No cross-tenant read/write by host, ID, filter, file URL or job substitution; no two successful check-ins for one registration; 30,000-registration test size, 50 scanners and 25 scans/s burst pass; dashboard p95 ≤5s; RPO ≤5min/RTO ≤30min; event-window availability plan supports 99.95% objective.
- **Testing requirements:** Automated tenant/role matrix, concurrency and abuse tests, 10-minute burst plus soak with concurrent import/send/export, restore drill, privacy purge audit, independent security review.
- **Definition of done:** Release evidence reports measured results and unresolved risks with owners; any failed approved target blocks launch or requires explicit revised approval.

#### M6-03 — Complete cross-device experience and pilot readiness
- **Objective and scope:** Run accessibility and device/browser acceptance across public registration, tenant/platform admin, scanner, billing, messaging and reports; conduct a staged event pilot and support rehearsal.
- **Dependencies:** M0-03 visual approval; all M2–M5 user paths; M6-01; G-02/G-05 final operating policies.
- **Acceptance criteria:** WCAG 2.2 AA target is evidenced for supported flows; 320px/200% zoom and light/dark/tenant themes reflow; scanner works on approved personal and organizer devices; ticket delivery, domain, payment and connectivity failures have clear support routes.
- **Testing requirements:** Keyboard/screen-reader and contrast review, representative phones and network conditions, camera permission cases, end-to-end event rehearsal including copied QR, duplicate gates, export/deletion, billing failure and incident simulation.
- **Definition of done:** Product, security/privacy, design, and operations sign a pilot report and release checklist; remaining issues are triaged against launch criteria.

## 5. Release acceptance and traceability

**Production release gate:** All M0 decisions affecting launch are recorded; M1–M5 tasks meet their own definition of done; M6-01/02/03 evidence is accepted; a representative staging event runs from tenant/domain setup through registration, delivery, check-in, dashboard, messaging, reports, and purge simulation. A live-event support owner and rollback route are assigned. This is an acceptance gate, not authorization to deploy.

| Requirement / decision | Planned tasks | Launch disposition |
|---|---|---|
| F-01/F-02/F-13/F-14; N-03/N-08; D-01 | M1-02/03/05, M2-01/02/03/04, M3-04, M6-03 | Multi-tenant, multi-event, branded custom-domain administration. |
| F-03/F-05; N-01; D-03 | M0-02, M3-02, M4-02, M6-02 | Signed non-PII QR proposal, ticket lifecycle and online single use; G-03 approval needed. |
| F-04; D-10 | M3-01/03/04 | Self and bulk registration with independently unique email/phone. |
| F-07; N-05; D-04 | M1-03, M4-01/03, M6-03 | Assigned gate staff on supported personal/organizer devices. |
| F-09/F-12; N-02/N-06; D-02/D-05/D-12 | M4-02/03/04, M6-01/02 | Confirmed online scan attempts, live metrics and approved service objectives. |
| F-10; D-07 | M5-01/04/05, M2-02 | Email/SMS/WhatsApp with policy, providers and usage controls. |
| F-11; N-07; D-06/D-11 | M5-02/03 | CSV/PDF, self-service privacy, 90-day detail removal and anonymous history. |
| F-13; D-13 | M2-02 | Paystack subscriptions and NGN; terms require G-05. |
| F-06/F-08/N-04; offline part of F-09 | No launch task | Deferred by D-02. No provisional offline acceptance or sync. |

## 6. Work deliberately left outside this plan

Multi-session or multi-day attendance, re-entry, group/shared-contact registration, identity checks beyond QR, native apps, offline admission/sync, direct database-per-tenant migration, and cross-tenant participant browsing by platform staff are not approved launch features. They require separate requirements, security and privacy review before tasks are added.
