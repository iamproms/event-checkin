# M1-05 shared UI primitives

The approved Quiet Precision foundation is in `tokens.css`; interaction and layout rules are in `primitives.css`. Import from `src/ui/index.ts`. The isolated examples are served at `/ui-lab.html` during development and are not included in the production Vite entry.

| Primitive | Contract |
|---|---|
| `Button` | Primary, secondary, tertiary, destructive; native disabled for unavailable actions; loading stays focusable with `aria-disabled`/`aria-busy`, visible loading text and blocked activation; `touchCritical` keeps a 44×44px minimum. |
| `Field` | Persistent label, optional hint/error, `aria-invalid`, associated descriptions, and announced errors. Use native input types/autocomplete. |
| `Status` | Semantic tone, explicit title and instruction. Pass `announce` only for a new decision; avoid repeated scanner announcements. |
| `NavItem` | Native link with neutral selected fill and `aria-current="page"`. |
| `Dialog` | Native modal dialog with focus containment, Escape close, and focus return. Parent owns open state. |
| `Progress` | Labelled native progress element with determinate or indeterminate value and visible text. |

Primitives accept presentation semantics only. Feature adapters map approved domain states to label, tone, and instruction using [state vocabulary v1](../../../docs/DECISIONS/M0-02_STATE_VOCABULARY_V1.md). They must not infer domain outcomes from colors. No scanner, event, billing, or messaging business logic belongs in this package.

`initializeTheme()` reads the same-origin preference (`event-checkin-theme`). With no explicit choice it resolves `System` from `prefers-color-scheme`; explicit Light or Dark choices persist. `ThemeControl` exposes all three states and listens for operating-system changes while System is active. The pre-render `theme-init.js` applies the same algorithm to avoid a wrong-theme flash. Compact density is a container-level `data-density="compact"` option for suitable admin interfaces; primary gate actions always use `touchCritical`. Tenant branding may vary approved action surfaces after contrast validation but must never redefine status, focus, or scan-result tokens.

Run `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:tokens`, and `npm run test:ui`. The browser suite covers isolated components, auth request behavior, keyboard/focus, 320px reflow, doubled text, theme persistence, axe checks, contrast, and rendered pixel/geometry assertions. Screenshot attachments are retained on test failures for manual review. Automated checks do not replace screen-reader and browser zoom spot checks.
