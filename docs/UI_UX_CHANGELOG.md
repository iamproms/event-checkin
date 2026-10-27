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

- The implementation direction and all remaining phases were approved before visual implementation began.

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
- Taste browser inspection of the design-system preview: 0 failures and 2 advisory warnings.
- The remaining Taste warnings are expected for the approved warm-neutral canvas and the intentionally long component-reference page.
- Desktop, tablet, and mobile preview captures were visually inspected; no clipping, unintended overlap, or horizontal overflow was observed.
- Preserved a platform overview before capture and added updated platform and design-system captures under `docs/screenshots/` for review.
- Renamed the overview action to “Open provisioning” after the full suite identified an accessible-name collision with the Organizations navigation link.
- The interrupted organizer workflow edits remain outside the Phase 2 commits and are documented for Phase 3 review.

## Backend dependencies

- Structured authentication lockout reason and retry metadata.
- Structured scanner rejection and event-window reason codes.
- Authoritative platform aggregate and operations telemetry APIs.
- Report formats beyond the existing CSV export.
- Communications and subscription service contracts.
- Background job status detail for precise bulk-operation progress.
