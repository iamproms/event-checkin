# UI/UX Audit

**Branch:** `feat/platform-ui-ux-overhaul`  
**Worktree:** `.feature-branches/platform-ui-ux-overhaul`  
**Audit date:** 2026-10-27  
**Status:** Phase 1 complete; visual implementation awaits approval.

## Executive summary

The current frontend has a sound visual foundation and several working operational flows, but it behaves like a set of related applications rather than one product. Authentication, the platform console, organizer workspace, gate scanner, and legacy management pages each use different shells or control styles. Event context is local to each screen, some administration metrics are explicitly synthetic, and several error paths can show technical messages.

The recommended direction is **Quiet Operations**: retain the approved warm neutral and deep evergreen system, use a framed application shell, make data dense screens easier to scan, and reserve strong color for status and high attention actions. The image references contribute composition, density, and contrast ideas. They are not used as decorative assets.

The first implementation priority is the shared foundation: tokens, primitives, shell, navigation, safe feedback, and validated event URL state. Core workflows can then move onto that foundation without changing APIs or business rules.

## Sources reviewed

### Product references

Every image in `inspo/` was inspected.

| Reference | Useful direction | Deliberate adaptation |
| --- | --- | --- |
| `05a3f666...jpg` | Split authentication composition, compact form, restrained footer | Retain product colors and remove promotional or fabricated metrics |
| `9acfa779...jpg` | Strong image-to-form balance, sparse controls, clear hierarchy | Use a brand surface that works without an external marketing image |
| `781138bc...jpg` | Compact labeled navigation, dense operational overview, strong contrast | Use orange only for warnings or exceptional attention |
| `84200885...jpg` | Balanced module grid and clear dark-theme hierarchy | Flatten excessive panels and avoid ornamental charts |
| `a9c8cb3c...jpg` | Precise tables, compact sidebar, information-rich dark surfaces | Preserve readable spacing and WCAG contrast at smaller sizes |

### Existing design guidance

- `docs/DESIGN_SYSTEM.md`
- `docs/design-system-preview.html`, inspected at desktop and mobile sizes
- `docs/DECISIONS/G-07_VISUAL_FOUNDATION.md`
- `docs/DECISIONS/G-08_EVENT_FIRST_PRODUCT_EXPERIENCE.md`
- `frontend/src/ui/README.md`

The approved **Quiet Precision** foundation remains appropriate: Inter, warm neutral surfaces, deep evergreen accent, restrained radii, visible focus, minimal shadow, and semantic status colors. The overhaul should extend and consistently apply it.

### Installed design skills

- `emil-design-eng` by Emil Kowalski: applied to interaction timing, focus behavior, button feedback, overlay behavior, reduced motion, and information hierarchy.
- `design-taste-frontend` from Leonxlnx/taste-skill: applied to application-screen composition, density, mobile folding, color restraint, and removal of generic dashboard patterns.
- Taste direction generated for this work: `framed-sheet`, SMB admin, retaining the current palette and type. It recommends a compact top bar, a 220 to 263 px sidebar, a white or dark content sheet, 24 px content padding, and less than 3% accent color.

## Current architecture

The frontend is a Vite and React 19 multi-entry application using plain CSS and shared CSS variables. It does not currently use a client routing library.

| Entry | Purpose | Current shell |
| --- | --- | --- |
| `index.html` | Sign in and authentication | `AuthShell` |
| `platform-console.html` | Platform administration | `AppShell` |
| `workspace.html` | Organizer workspace | `AppShell` |
| `gate.html` | Gate scanning | Dedicated scanner shell |
| `platform.html` | Legacy organization provisioning | Legacy management layout |
| `events.html` | Event editing and publishing | Legacy event layout |
| `domains.html` | Domain configuration | Legacy management layout |
| `branding.html` | Branding configuration | Dedicated legacy layout |
| `register.html` | Participant registration | Public registration layout |
| `ui-lab.html` | Component specimens | UI lab |

Shared primitives exist under `frontend/src/ui`, while product components and styles live under `frontend/src/product`. Organizer route state is hash based. Each event-scoped screen currently loads and selects events independently.

## Findings and recommendations

The format below records the current state, intended change, and reason.

### Foundation and shell

| Before | After | Why |
| --- | --- | --- |
| Shared tokens exist, but product and legacy pages redefine controls, spacing, and surfaces | One token layer and one set of field, button, status, table, dialog, and feedback primitives | Reduces visual drift and makes state behavior consistent |
| Organizer and platform use a framed shell; legacy event, domain, branding, and provisioning pages use separate shells | Shared shell variants for platform, organizer, operational scanner, and public/auth contexts | Keeps workflows recognizable without forcing every audience into one identical layout |
| Theme is a native select with no indication of the resolved system theme | Compact System, Light, Dark selector with current resolved state and accessible labels | Makes the result predictable and usable by keyboard |
| Page headings often add uppercase context labels | Noun-led titles, concise supporting copy, breadcrumbs where hierarchy matters | Improves scanning and follows the approved product voice |
| Mobile navigation works as a drawer, but route and event context are not visible enough | Drawer includes workspace identity, current event context, and clear selected state | Prevents users from losing context on narrow screens |

### Authentication and onboarding

| Before | After | Why |
| --- | --- | --- |
| Auth shell shows a fictional expected-attendance figure | Branded split composition using product promise, security posture, and real session state only | Removes invented operational data |
| Password fields have no show or hide control | Reusable accessible `PasswordField` with visible label, pressed state, and retained focus | Supports password managers and reduces entry errors |
| Lockout is shown as a generic request error | Dedicated lockout message with recovery guidance; use retry duration when the API supplies it | Makes the next action clear without exposing internals |
| Invitation and onboarding screens vary in structure | Shared auth/onboarding frame, progress context, validation summary, and completion state | Creates a coherent path into the product |

### Event context and organizer workspace

| Before | After | Why |
| --- | --- | --- |
| Each screen defaults independently to the first published event | `EventWorkspaceProvider` validates `#route?event=<id>` and supplies one selected event to all event-scoped screens | Preserves event choice through navigation, refresh, and deep links |
| Dashboard, check-in, and reports reuse much of the same attendance layout | Purpose-specific overview, live attendance, and reports compositions built from shared data modules | Matches each task while preserving common logic |
| Event directory opens a visually separate editor with local-only selection | Keep the active editor workflow, align its shell and deep-link the selected event | Preserves capability and reduces navigation discontinuity |
| Event IDs are sometimes primary input or context | Show event names and status first; place IDs in copyable support details | Keeps technical identifiers available without making them the normal navigation model |

### Participants and imports

| Before | After | Why |
| --- | --- | --- |
| Import controls, preview, and results compete for attention on one dense surface | A staged import flow: file, mapping or validation, confirmation, progress, and results | Clarifies long-running work and recovery paths |
| Validation error codes can appear directly in the UI | Map known codes to readable messages and fall back to a safe generic error with a support reference | Prevents raw implementation details from reaching users |
| Loading and empty table states are mostly row text | Table skeletons for initial load; intentional empty state above the table body | Keeps columns stable and gives a next action |

### Tickets

| Before | After | Why |
| --- | --- | --- |
| Finding a ticket requires event and registration UUIDs | Participant-led ticket directory with event context; IDs remain in advanced details | Matches the operator's mental model |
| Bulk issue and email actions use native confirmation | Product dialog with scope, count, consequences, progress, and result summary | Improves clarity for consequential actions |
| Issuing and sending have limited progress detail | Persistent operation status with queued, processing, completed, partial, and failed states where the API exposes them | Prevents duplicate submissions and uncertain completion |

### Live attendance and reports

| Before | After | Why |
| --- | --- | --- |
| Valid counts are shown as a four-cell metric strip, with limited gate comparison | Emphasize checked in, remaining, freshness, gate throughput bars, and recent outcomes using only returned data | Makes the operational state easier to read without inventing a time series |
| Empty recent activity resembles an incomplete table | Calm zero-state explaining that scans will appear after server confirmation | Sets expectations |
| Reports currently expose CSV export through the attendance layout | Dedicated reports page with live CSV export; unavailable report formats use an honest Coming soon state | Separates current capability from future work |

### Gate staff and scanner

| Before | After | Why |
| --- | --- | --- |
| Gate staff actions use raw enum labels and native confirmation | Human labels, scoped assignment summaries, shared confirmation dialog, and clear invitation progress | Improves safety and consistency |
| Scanner feedback handles accepted, duplicate, revoked, and invalid outcomes, but unavailable cases are broad | Distinct visual outcomes for server-confirmed results; separate device, network, permission, and service-unavailable feedback | Gives staff an actionable next step |
| Scanner at 320 px is 4 px wider than its viewport | Remove the overflow and test at 320 px | Meets the documented responsive baseline |
| Loading spinner still rotates under reduced motion | Replace rotation with a static progress cue under `prefers-reduced-motion` | Honors user motion settings |

### Platform administration

| Before | After | Why |
| --- | --- | --- |
| Overview displays explicit demo counts and a synthetic trend chart | Show only verifiable readiness and live organization data; use unavailable states for missing aggregates | Removes fictional operational information |
| Operations displays synthetic incident and job totals | Honest service status plus documented backend dependency for unavailable telemetry | Prevents an inaccurate view of system health |
| Domain examples resemble active records | Mark examples as guidance or connect them to real organization-scoped data | Avoids confusing examples with production state |
| Subscription controls are disabled with sparse context | Restricted or Coming soon state with reason, owner, and available next action | Distinguishes permission, product availability, and service failure |

### Error handling and feedback

| Before | After | Why |
| --- | --- | --- |
| Several screens render `Error.message` from request helpers | Central safe error mapper with user copy, optional retry, and a support reference | Avoids raw server responses, JSON errors, or stack details |
| Success is often a toast-like message or inline text without a pattern | Use inline confirmation near the changed object; reserve transient notices for background completion | Keeps feedback proportionate |
| Disabled controls frequently rely on disabled styling alone | Adjacent reason text or an accessible tooltip for compact controls | Explains unavailable actions to mouse, touch, and keyboard users |

## Screen and state coverage

| Area | Loading | Empty | Error | Success | Restricted or Coming soon | Long-running |
| --- | --- | --- | --- | --- | --- | --- |
| Authentication | Button progress | N/A | Validation, credentials, lockout | Redirect or recovery sent | Invitation expired or invalid | Recovery send |
| Platform console | Page skeleton | No organizations | Safe retry panel | Organization created | Billing and unsupported telemetry | Provisioning |
| Events | List and editor skeleton | Create first event | Retry with retained input | Saved or published inline | Unsupported integrations | Publishing |
| Participants | Table and preview skeleton | Add or import participants | Row and file errors | Import summary | Permission restrictions | Import progress |
| Tickets | Directory skeleton | No eligible tickets | Retry and partial failure | Issued or sent summary | Provider unavailable | Bulk issue and email |
| Live attendance | Stable metric skeleton | No registrations or scans | Stale-data banner with retry | Freshness confirmation | Event not active | Refresh and export |
| Gate staff | List skeleton | Invite first staff member | Safe action error | Invitation or assignment confirmation | Role restrictions | Bulk invite if supported |
| Scanner | Camera and verification progress | No assignment | Device, network, invalid, unavailable | Accepted | Assignment or event restriction | Server verification |
| Reports | Export progress | No data for selected event | Retry | Download ready | Future formats | CSV generation |
| Branding/settings | Form skeleton | Defaults | Field and save error | Saved inline | Role restriction or unsupported setting | Asset upload if supported |

## Accessibility and responsive findings

- Existing primitives provide visible focus and generally good labels. The baseline Playwright accessibility checks pass.
- Show or hide password controls, explained disabled states, and dialog focus handling remain missing or inconsistent.
- Tables need explicit numeric alignment, useful captions, and a verified mobile transformation.
- The gate screen currently exceeds a 320 px viewport by 4 px.
- Keyboard checks need to cover the navigation drawer, event switcher, dialogs, file import, and scanner controls.
- Dark and light contrast should be verified after token changes, including status colors on tinted surfaces.
- Mobile screens must keep primary actions reachable without fixed elements covering content.

## Data integrity and backend dependencies

The frontend will not simulate missing capabilities. These items need backend support for a complete experience:

1. **Authentication lockout metadata:** a structured error code and retry timestamp or duration are needed for an accurate countdown.
2. **Scanner rejection reasons:** structured reason codes are needed to distinguish an inactive event, an outside-window scan, a disabled gate, and a general service outage.
3. **Platform aggregates and operations telemetry:** live totals, trends, queues, and incidents require authoritative APIs.
4. **Additional report formats:** PDF or scheduled reports require generation and delivery support. CSV export already works.
5. **Communications and subscription management:** these remain Coming soon until service contracts exist.
6. **Background operation detail:** precise progress for ticket email and other bulk jobs depends on job status endpoints. The UI can show request and completion state with current APIs.

There is also a coordination dependency: another active workstream contains uncommitted organization directory, privacy notice, API safety, and participant import changes in the main worktree. This feature worktree will not copy or overwrite them. Integration should occur after that work is committed, followed by targeted conflict review.

## Baseline verification

Run from the isolated worktree before visual implementation:

| Check | Result |
| --- | --- |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm run test:tokens` | Passed, 2 tests |
| Taste skill linter | 0 failures, 8 warnings |
| `npx playwright test` | 34 passed, 1 failed |

The Playwright failure is the existing 320 px gate overflow (`scrollWidth` 324). Existing Playwright screenshots for organizer desktop light, platform desktop dark, and gate mobile dark were visually inspected. The design-system preview was rendered and inspected at desktop and mobile sizes.

## Approval recommendation

Proceed with the component architecture and phases in `docs/UI_UX_IMPLEMENTATION_PLAN.md`. Begin with the shared foundation and event URL state, then redesign the workflows on top of those stable contracts.
