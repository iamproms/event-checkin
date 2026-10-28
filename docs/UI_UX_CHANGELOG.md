# UI/UX Changelog

This file records the work completed on `feat/platform-ui-ux-overhaul`. Entries distinguish implementation, verification, and known dependencies.

## 2026-10-27: Phase 1 audit and planning

### Added

- Completed a repository, worktree, frontend architecture, route, component, and styling audit.
- Inspected every reference in `inspo/`.
- Reviewed the existing design system, design-system preview, and G-07 and G-08 design decisions.
- Applied guidance from the installed `emil-design-eng` and `design-taste-frontend` skills.
- Recorded the proposed Quiet Operations direction and component architecture.
- Documented screen-specific loading, empty, error, success, restricted, Coming soon, and long-running states.
- Separated backend dependencies from frontend implementation work.

### Verified

- `npm run typecheck`: passed.
- `npm run lint`: passed.
- `npm run test:tokens`: passed, 2 tests.
- Taste skill linter: 0 failures and 8 warnings.
- Full Playwright baseline: 34 passed and 1 failed.
- Existing organizer desktop light, platform desktop dark, and gate mobile dark screenshots were visually inspected.
- The design-system preview was rendered and inspected at desktop and mobile sizes.

### Existing issue recorded

- Gate mobile layout exceeds the 320 px viewport by 4 px. This is the single failing Playwright baseline check.

### Coordination note

- The main worktree has unrelated and uncommitted organization directory, privacy notice, API safety, and import changes from another workstream. No files from that worktree were modified, copied, reset, or discarded. Integration will wait until those changes are committed and can be reviewed safely.

### Approved scope

- The Quiet Operations direction and Phase 2 design-foundation work were approved before visual implementation began. Later phases require separate review and approval.

## 2026-10-27: Phase 2 design foundation

### Implemented

- Added reusable password visibility, select, textarea, skeleton, inline progress, and screen-state primitives.
- Replaced the native theme select with an accessible System, Light, Dark segmented control that reports the resolved theme.
- Added button loading indicators, disabled-reason support, numeric table alignment, stable loading rows, and explicit empty table content.
- Added safe JSON response handling and status-based user messages so raw server responses and parsing errors do not reach product screens.
- Removed the fictional attendance figure from authentication.
- Added keyboard focus restoration and Escape handling to the mobile navigation drawer.
- Added event context to the organizer sidebar.
- Added `EventWorkspaceProvider` with validated `#route?event=<id>` state that persists across navigation and refresh.
- Added reusable breadcrumbs and shared error, Coming soon, and restricted-state adapters.
- Expanded the UI laboratory with password and screen-state specimens.

### Tests added or updated

- Added keyboard coverage for showing and hiding a password while preserving its value.
- Added organizer event-selection persistence coverage across routes and refresh.
- Updated theme tests for the segmented control.
- Expanded narrow-screen diagnostics to identify intrinsic-width overflow.

### Visual inspection

- Inspected refreshed organizer desktop light, platform desktop dark, and gate mobile dark screenshots after the foundation changes.

### Recovery completion

- Replaced synthetic platform totals, charts, domains, job counts, delivery backlogs, and alerts with live readiness values or explicit unavailable states.
- Added shared success and unavailable screen-state variants and exposed them in the UI laboratory and design-system preview.
- Replaced the subscription placeholder controls with an honest Coming soon state and the administrator placeholder with a restricted state.
- Routed scanner failures through the shared safe-error mapper so raw server payloads and parsing failures are not presented to gate staff.
- Removed scanner spinner animation when reduced motion is requested.
- Updated the Quiet Operations preview with password visibility, progress, and all operational screen-state specimens.
- Reduced floating-surface shadows after browser inspection and retained flat base and grouped surfaces.

### Phase 2 verification

- TypeScript: passed.
- ESLint: passed.
- Token tests: passed, 2 tests.
- Targeted Playwright interaction, accessibility, narrow-screen, platform, and scanner checks: passed, 7 tests.
- Full Playwright suite against the committed Phase 2 snapshot: passed, 37 tests.
- Taste source linter across `frontend/src`: 0 failures and 8 advisory warnings.
- Taste browser inspection of the design-system preview: 0 failures and 2 advisory warnings.
- The remaining Taste warnings are expected for the approved warm-neutral canvas and the intentionally long component-reference page.
- Source advisories cover four functional overlay or selected-control shadows, two technical monospace uses, the existing public-registration section label, and eight em dashes reported as one copy warning.
- Desktop, tablet, and mobile preview captures were visually inspected; no clipping, unintended overlap, or horizontal overflow was observed.
- Preserved a platform overview before capture and added updated platform and design-system captures under `docs/screenshots/` for review.
- Renamed the overview action to “Open provisioning” after the full suite identified an accessible-name collision with the Organizations navigation link.
- The interrupted organizer workflow edits remain outside the Phase 2 commits and are documented for Phase 3 review.

## 2026-10-27: Phase 3 core workflows

### Organizer overview and events

- Replaced the attendance-first dashboard with an event-aware operational overview using only selected-event and attendance API data.
- Added event context, lifecycle, schedule, location, registration mode, and direct next actions without invented activity.
- Added validated event editor deep links through `/events.html?event=<id>` while retaining the existing event APIs and editor panels.
- Routed unexpected event-editor failures through the shared safe error mapper.

### Participants and import

- Improved selected-event context, loading, search-empty, error, pagination, ticket-status, and import-entry states.
- Converted internal import validation codes into readable corrective messages.
- Added determinate progress feedback for background import processing and explicit completion feedback.
- Preserved custom-field mapping, notice version, lawful basis, duplicate handling, and import API payloads.

### Tickets

- Replaced UUID-first ticket lookup with the selected event's participant directory.
- Added server-authoritative delivery summaries, email preview, operation notices, and explanations for disabled issue and email actions.
- Added shared confirmation dialogs for issue, send, resend, reissue, and revoke operations.
- Kept event and registration identifiers available inside collapsed support details.
- Cleared participant selection when the event changes so a registration is never queried under a stale event.

### Live attendance and gate staff

- Separated overview, live attendance, and export compositions.
- Added proportional gate-throughput bars, recent outcome status, freshness, export progress, and export success feedback using returned API values.
- Added gate and staff loading, empty, error, disabled, and invitation-success states.
- Replaced native assignment and revocation confirmation with the shared focus-restoring dialog.

### Verification

- TypeScript: passed.
- ESLint: passed.
- Token tests: passed, 2 tests.
- Full Playwright suite: passed, 41 tests.
- Added tests for event editor deep links, readable import issues, participant-based ticket operations, dialog focus restoration, and 320 px organizer workflow reflow.
- Automated WCAG 2.2 AA checks passed for participants, tickets, live attendance, and gate staff at 320 px.
- Taste source linter: 0 failures and 8 advisory warnings; the advisory categories are unchanged from Phase 2.
- Visually inspected organizer overview and tickets at desktop, live attendance at tablet width, and participants and gate staff at mobile width.
- Added review captures under `docs/screenshots/phase3-*.png`.

### Approval boundary

- Phase 3 is complete for review. Phase 4 proceeded under the subsequent continuation approval.

## 2026-10-28: Phase 4 supporting interfaces

### Platform administration

- Added a dedicated privacy-notice route and an explicit backend-required state instead of implying editable policy data.
- Reworked organization provisioning around the shared fields, buttons, loading skeleton, success state, and safe operation feedback.
- Kept the connected organization-creation and invitation-resend workflow while clearly separating the unavailable organization directory and detail APIs.
- Added signed-in permission context and restricted-access guidance without inventing organization counts or cross-tenant records.
- Preserved the live readiness overview and removed the remaining synthetic-platform framing from supporting routes.

### Authentication and onboarding

- Applied the shared password visibility control to the active legacy platform sign-in.
- Added incomplete invitation and password-reset link handling that never presents a credential submission form without its token.
- Added stronger new-password guidance and six-digit MFA input constraints while preserving all authentication endpoints and security behavior.
- Kept lockout copy honest when the backend supplies no precise retry time and cleared authenticator input when changing verification modes.
- Preserved loading, disabled, validation, recovery, MFA enrollment, session-expiry, and completion messaging.

### Gate scanner

- Added distinct camera permission, missing-device, unsupported-browser, insecure-context, offline, and unpublished-event feedback.
- Refined accepted, duplicate, revoked, invalid, and network-unconfirmed outcomes so only a server-confirmed accepted result permits admission.
- Renamed the unstructured invalid outcome to “Ticket not accepted” and explicitly avoids inferring a rejection reason the API did not return.
- Kept the mobile operational composition readable at 320 px and retained reduced-motion behavior for active scanning feedback.

### Reports, branding, settings, and legacy workflows

- Kept attendance CSV as the connected report and labeled unimplemented report formats as Coming soon.
- Replaced sample organization branding and fallback domain values with explicit unavailable or restricted states.
- Added shared navigation and operation feedback to the active branding and domain management pages.
- Added honest unavailable states for profile editing and self-service privacy operations.
- Routed public registration and supporting-management failures through safe user messages instead of raw API detail.
- Preserved active routes, working controls, request payloads, and backend contracts.

### Interaction-state coverage

- Added focused coverage for restricted platform provisioning, unavailable organization and privacy data, incomplete authentication links, password visibility, scanner rejection outcomes, and connected-versus-unavailable reporting and settings states.
- Verified loading, empty, error, success, restricted, disabled, Coming soon, and asynchronous operation feedback through existing and Phase 4 deterministic fixtures.
- Added route-level focus restoration and reduced-motion verification for the supporting-interface drawer.

### Verification

- TypeScript: passed.
- ESLint: passed.
- Production build: passed, 79 modules transformed.
- Token tests: passed, 2 tests.
- Playwright: passed, 49 tests across all eight spec files in one final-tree run.
- Phase 4 focused Playwright suite: passed, 8 tests.
- Automated WCAG 2.2 AA checks passed across representative supporting screens at 320 px.
- Taste source linter: 0 failures and 8 advisory warnings. The categories remain four intentional functional shadows, two technical monospace uses, one existing public-registration eyebrow, and one aggregate em-dash copy warning.
- Keyboard focus restoration and reduced-motion drawer behavior passed at the route level.
- Inspected a 1440 px platform provisioning view, 768 px attendance reports view, 320 px authentication view, and 390 px server-rejected scanner result. No clipping, overlap, or unintended horizontal overflow was observed.
- Added `phase4-platform-organizations-desktop.png`, `phase4-reports-tablet.png`, `phase4-auth-mobile-320.png`, and `phase4-gate-invalid-mobile.png` under `docs/screenshots/`.
- Refreshed `platform-desktop-dark.png`; `platform-desktop-dark-before.png` remains the relevant comparison showing the removed synthetic totals and chart.

### Phase 4 boundary

- Phase 4 is complete for review. No merge or push was performed.
- Cross-browser and expanded manual assistive-technology verification remain recommended Phase 5 work.

## Backend dependencies

- Structured authentication lockout reason and retry metadata.
- Structured scanner rejection and event-window reason codes.
- Authorized platform organization directory and organization-detail APIs.
- Platform privacy-notice read, version, publish, and history APIs.
- Authoritative platform aggregate and operations telemetry APIs.
- Report formats beyond the existing CSV export.
- Communications and subscription service contracts.
- Background job status detail for precise bulk-operation progress.
- Organization profile editing and self-service privacy-operation contracts.
