# UI/UX Implementation Plan

**Branch:** `feat/platform-ui-ux-overhaul`  
**Status:** Proposed for approval  
**Constraint:** Frontend-only changes unless a separate backend change receives explicit approval.

## Design direction: Quiet Operations

The product will extend the existing Quiet Precision system into a consistent operational interface.

### Visual language

- **Composition:** a compact product bar and labeled side navigation frame a calm content sheet. Public and authentication pages use a split composition. The scanner uses a focused operational shell.
- **Typography:** retain Inter. Use a restrained type scale with tabular numerals for operational counts. Page titles are nouns or short task labels. Supporting copy remains concise.
- **Color:** warm neutral structure, deep evergreen for the main action and verified positive state, semantic colors for warnings and errors, and rare amber for high attention conditions. Dark theme uses charcoal surfaces and keeps the same hierarchy.
- **Spacing:** use the established 4 px base scale. Standard page padding is 24 px on desktop, 16 px on compact screens, and 12 px at the narrowest supported widths.
- **Surfaces:** prefer section rules, table groups, and flat information regions. Cards are used when their border communicates a real grouping.
- **Data:** show authoritative values only. Empty, stale, and unavailable data receive explicit states.
- **Motion:** use short opacity and transform transitions for overlays and direct manipulation. Frequent actions remain immediate. Reduced motion removes nonessential movement.

### Responsive model

| Width | Layout behavior |
| --- | --- |
| 1200 px and above | Persistent sidebar, full content sheet, multi-column operational layouts |
| 768 to 1199 px | Compact sidebar or drawer based on available content width; two-column modules collapse selectively |
| 480 to 767 px | Drawer navigation, single-column forms and data regions, actions wrap by priority |
| 320 to 479 px | Edge-to-edge content sheet, 12 px gutters, stacked actions, table alternatives with complete labels |

## Proposed component architecture

### Foundation

1. **Tokens**
   - Consolidate color, type, space, radius, border, focus, layer, motion, and breakpoint variables.
   - Add semantic aliases for surface, text, action, status, selection, and data visualization.
   - Define equivalent light and dark values without changing status meaning.

2. **Controls**
   - `Button` with primary, secondary, quiet, danger, icon, loading, and disabled-reason behavior.
   - `TextField`, `PasswordField`, `SelectField`, `Textarea`, `Checkbox`, and `FileDropzone` with shared help and validation structure.
   - `ThemeControl` as an accessible compact choice among System, Light, and Dark.

3. **Feedback and state**
   - `InlineSpinner`, `Skeleton`, `Progress`, `Notice`, `StatusBadge`, and `OperationStatus`.
   - `EmptyState`, `ErrorState`, `ComingSoonState`, and `RestrictedState` with a common hierarchy.
   - A safe API error mapper that never renders raw server payloads.

4. **Navigation and overlays**
   - `AppShell`, `WorkspaceSwitcher`, `EventSwitcher`, `Breadcrumbs`, `NavItem`, and `MobileNav`.
   - `Dialog`, `Drawer`, and `Menu` with focus restoration, Escape handling, and reduced motion.

5. **Data display**
   - `DataTable` with captions, sortable header affordances where supported, numeric alignment, stable loading rows, empty content, and responsive row details.
   - `Metric`, `DefinitionList`, `ActivityList`, `ThroughputBar`, and `CopyableIdentifier`.

### Product state

`EventWorkspaceProvider` will become the single frontend owner of organizer event selection:

1. Read `event` from the hash query.
2. Load events using the existing API.
3. Validate that the requested event is accessible.
4. Fall back to the first appropriate event only when the URL is missing or invalid.
5. Replace the hash query with the validated event ID.
6. Preserve the query during route changes.
7. Expose the event name, status, and refresh action to pages and the shell.

This keeps URLs shareable and refresh safe without adding a routing dependency or changing backend behavior.

## Phase 1: audit

### Deliverables

- Complete reference, skill, design-system, architecture, and route review.
- Record baseline test results and existing failures.
- Separate UI fixes from missing backend capabilities.
- Propose the design direction, component architecture, screen plan, and verification gates.

### Completion criteria

- `docs/UI_UX_AUDIT.md`, this plan, and `docs/UI_UX_CHANGELOG.md` exist in the isolated worktree.
- No substantial visual implementation has begun before approval.

## Phase 2: design foundation

### Work

- Normalize tokens and remove duplicated component styling.
- Add the missing control, feedback, state, navigation, and data-display primitives.
- Update `AppShell`, authentication frame, navigation, breadcrumbs, mobile drawer, and theme control.
- Add safe frontend error mapping.
- Add `EventWorkspaceProvider` and validated hash-query state.
- Update `DESIGN_SYSTEM.md`, UI documentation, and the design-system preview as behavior changes.

### Verification

- Token contract tests.
- Primitive interaction and accessibility tests.
- Keyboard checks for theme, navigation, event selection, dialog, and drawer.
- Desktop and 320 px visual inspection in both themes.

### Proposed commit

`feat(ui): consolidate visual foundations and workspace shell`

## Phase 3: core workflows

### Organizer overview and events

- Build an event-aware overview from existing authoritative sources.
- Make recent actions and the next operational tasks clear.
- Align the event directory and active legacy editor with the shared shell.
- Deep-link the selected event and retain the existing creation and publishing contracts.

### Participants and CSV import

- Clarify participant browsing and ticket state in the selected event.
- Convert import into a staged workflow with readable validation issues.
- Add stable loading, no-participant, import failure, partial success, and completion states.
- Preserve the current import API and duplicate-handling rules.

### Tickets

- Replace UUID-first navigation with participant and event context.
- Keep copyable IDs in advanced support details.
- Add confirmation dialogs and operation feedback for issuance and email delivery.
- Represent partial failures using only API-returned results.

### Live attendance

- Separate the live attendance composition from overview and reports.
- Emphasize attendance, remaining capacity, data freshness, gate throughput, and recent outcomes.
- Use proportional visuals computed from returned counts; do not synthesize historical series.
- Preserve the existing 15-second refresh and CSV export behavior.

### Gate staff

- Improve invitation and assignment hierarchy.
- Explain empty, restricted, and disabled states.
- Replace native confirmation with the shared dialog.

### Verification

- Existing event creation, publication, participant import, ticket issue, ticket email, invitation, live attendance, and export tests remain green.
- Add focused tests for URL event persistence, readable import errors, dialogs, and long-running action states.
- Inspect representative desktop, tablet, and mobile screens.

### Proposed focused commits

- `feat(ui): preserve selected event across organizer workflows`
- `feat(ui): redesign participant and ticket operations`
- `feat(ui): improve live attendance and gate staffing`

## Phase 4: supporting interfaces

### Platform administration and organization management

- Remove synthetic totals and charts.
- Use live health and organization records already supported by APIs.
- Provide explicit unavailable states for missing telemetry, subscriptions, and cross-organization domain data.
- Integrate the concurrent organization and privacy work only after it is committed and reviewed.

### Authentication, recovery, invitation, and onboarding

- Apply the split authentication composition.
- Add accessible password visibility controls.
- Improve validation, lockout, expired invitation, recovery, and completion states.
- Remove fabricated event statistics.

### Scanner

- Fix 320 px overflow.
- Refine accepted, duplicate, invalid, revoked, device, network, and unavailable feedback.
- Keep server confirmation mandatory and preserve duplicate prevention.
- Show an honest general unavailable state until structured backend reason codes exist.

### Reports, branding, settings, and legacy pages

- Give CSV export a dedicated reports surface.
- Present unsupported report formats as Coming soon.
- Move active branding, domain, event, and platform workflows onto the shared visual language.
- Retain every working control and API contract.
- Make role restrictions explicit.

### Verification

- Test authentication, recovery, platform provisioning, branding, domain, registration, and scanner flows.
- Inspect auth desktop and mobile, platform desktop and mobile, scanner mobile, and public registration.
- Verify light and dark themes, keyboard order, focus restoration, and reduced motion.

### Proposed focused commits

- `feat(ui): align authentication and platform administration`
- `feat(ui): refine scanner feedback and supporting interfaces`

## Phase 5: verification and documentation

### Automated checks

- `npm run typecheck`
- `npm run lint`
- `npm run test:tokens`
- Full Playwright suite
- Taste skill linter

### Browser matrix

| Area | Desktop | Tablet | Mobile 390 px | Mobile 320 px | Light | Dark |
| --- | --- | --- | --- | --- | --- | --- |
| Auth and recovery | Yes | Yes | Yes | Yes | Yes | Yes |
| Platform console | Yes | Yes | Yes | Yes | Yes | Yes |
| Organizer shell | Yes | Yes | Yes | Yes | Yes | Yes |
| Events and participants | Yes | Yes | Yes | Yes | Yes | Yes |
| Tickets and attendance | Yes | Yes | Yes | Yes | Yes | Yes |
| Gate staff and scanner | Yes | Yes | Yes | Yes | Yes | Yes |
| Reports, branding, settings | Yes | Yes | Yes | Yes | Yes | Yes |
| Registration and onboarding | Yes | Yes | Yes | Yes | Yes | Yes |

### Interaction verification

- Keyboard-only route navigation and event selection.
- Visible focus and focus restoration after overlays close.
- Screen-reader labels for icon controls, password visibility, statuses, progress, and validation summaries.
- Loading, empty, error, success, Coming soon, restricted, and long-running states using deterministic test fixtures.
- No horizontal scrolling at 320 px except intentionally scrollable data regions.
- 200% zoom checks for primary workflows.
- Reduced-motion behavior for drawers, dialogs, menus, and progress indicators.
- Long English values, email addresses, identifiers, non-Latin names, and large counts.

### Documentation

- Update `docs/DESIGN_SYSTEM.md` and `docs/design-system-preview.html` to match the implementation.
- Maintain `docs/UI_UX_CHANGELOG.md` as each phase lands.
- Record remaining backend dependencies and any screens that could not be verified.

### Proposed final commit

`test(ui): verify responsive and accessible product workflows`

## Change boundaries

- Do not change authentication, authorization, database schemas, security behavior, or API contracts.
- Do not fabricate operational data or simulate successful backend work.
- Do not remove active legacy workflows before their replacement is complete.
- Keep unrelated refactoring out of this branch.
- Do not merge or push without approval.

## Approval gate

After this direction is approved, implementation starts with Phase 2 and proceeds in focused commits. Each phase will update the changelog with changed files, verified screens, automated checks, and open dependencies.
