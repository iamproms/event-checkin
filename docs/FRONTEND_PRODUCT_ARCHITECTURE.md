# Frontend product architecture

## Product frame

The product uses the approved Quiet Precision foundation with a **framed sheet** application shell: a warm, low-chroma evergreen frame holds the global navigation and 48px utility bar, while work sits on one bordered surface inset from the viewport. The product signature is the narrow vertical event timeline used across dashboards, event detail and gate readiness. It makes time—the critical constraint in registration and check-in—visible without turning every fact into a card.

Theme preference supports System, Light and Dark. System is the first-visit value and follows operating-system changes; explicit Light or Dark selections persist. Inter remains the product typeface; identifiers, timestamps and tabular values use tabular figures. Controls use 4px radii, structural surfaces use 8–16px radii, and shadows are reserved for dialogs and mobile navigation.

The urgent release path is event-first: shared sign-in, simple organizer onboarding, import-only event publication, email-only CSV import, explicit QR issuance and sending, server-confirmed gate redemption, live attendance and export. Billing, campaigns, and advanced platform analytics remain secondary destinations with truthful deferred states. [G-08](DECISIONS/G-08_EVENT_FIRST_PRODUCT_EXPERIENCE.md) records the scope and activation gates.

## Experiences and routes

| Experience | Entry point | Routes |
| --- | --- | --- |
| Platform Console | `/platform-console.html` | `#overview`, `#organizations`, `#domains`, `#subscriptions`, `#operations`, `#settings` |
| Organizer Workspace | `/workspace.html` | `#dashboard`, `#events`, `#participants`, `#tickets`, `#check-in`, `#gate-staff`, `#communications`, `#reports`, `#branding`, `#settings` |
| Public attendee | `/register.html?event=<slug>` | event information, registration, confirmation, unavailable and closed states |
| Gate | `/gate.html` | assignment, readiness, camera/manual scan, and server-confirmed result states |

The common `/` sign-in page selects authorized platform or tenant contexts after password verification. Shared-host account setup uses `/invite#token=…&tenant=…`. Existing `/platform.html`, `/events.html`, `/branding.html`, `/domains.html`, and `/register.html` routes remain valid. Live workspace destinations link to those focused workflows until their APIs can support a consolidated resource query.

## Shared architecture

- `src/product/AppShell.tsx`: responsive desktop sidebar, mobile navigation, utility bar, breadcrumbs, theme control and capability legend.
- `src/product/components.tsx`: page headers, capability banners, metric strips, tables, filters, empty states, timelines, charts and settings rows.
- `src/product/capabilities.ts`: typed `live | demo | unavailable` capability registry. Demo data never enters live API adapters.
- `src/product/demo-data.ts`: clearly synthetic preview records used only by demo screens.
- `src/product/router.ts`: small hash router that preserves independent HTML entry points and same-origin API/cookie behavior.

Backend authorization remains authoritative. Frontend route visibility is explanatory UX, not an access-control boundary. Platform administrators never receive implicit tenant participant access. On the shared host, a signed tenant-context cookie selects a route, while the tenant session, membership, MFA, and event permissions authorize it. Custom-domain and public registration resolution still use verified hostnames.

Shared-host password recovery sends a neutral response, derives a tenant routing hint from an active server-side membership, and places that hint in the emailed reset link. Reset completion still checks the single-use token and active membership before changing the global staff password. Platform-only account recovery remains an operator-assisted process until a separately reviewed platform reset flow exists.

## Capability matrix

| Product area | Capability | Notes |
| --- | --- | --- |
| Platform authentication and MFA | LIVE | Existing host-bound session, CSRF and MFA APIs |
| Shared organization creation and owner invitation | LIVE locally | Platform API creates an active tenant and single-use owner invite without per-tenant DNS; local Mailpit accepts the invitation, production transport remains disabled |
| Custom-domain onboarding | LIVE where provider configured | Existing domain APIs and proof/TLS state machine remain intact |
| Events and registration form configuration | LIVE | Existing event APIs plus import-only mode and generated slug |
| Branding | LIVE | Existing draft, preview, asset and publication APIs |
| Public registration | LIVE | Existing hostname-derived public API |
| Bulk ticket issuance and first send | LIVE locally | Separate idempotent actions; local Mailpit delivery only; provider acceptance differs from inbox delivery |
| Gate staff directory, reassignment and revocation | LIVE locally | Tenant admins see server-authorized memberships; moving staff revokes their current session and replaces their event/gate assignment |
| Ticket resend, reissue and revoke | LIVE | Existing ticket command APIs |
| Platform aggregate overview and full operations console | DEMO | Synthetic metrics are labeled and isolated |
| Organizer dashboard and participant administration | LIVE, unverified locally | Real registration and attendance APIs; synthetic operational totals are prohibited |
| Imports | LIVE, pending 0012 integration test | CSV/XLSX preview, email-only mapping, chunked commit, row errors; import-only records await explicit issuance |
| Gate selection, scanner and redemption | LIVE, unverified locally | Online-only, server-confirmed, atomic redemption across gates; bundled decoder covers browsers without native QR detection, pending real-device rehearsal |
| Communications | UNAVAILABLE | M5 campaign operations are deferred; no campaign can be sent |
| Basic attendance report/export | LIVE, unverified locally | Authorized event CSV and committed check-in metrics |
| Billing and subscriptions | UNAVAILABLE | M2-02 commercial decisions and APIs remain open |

The gate camera uses the browser's QR detector when available and bundles
[`jsqr` 1.4.0](https://github.com/cozmo/jsQR) as an Apache-2.0 fallback. Both
paths submit the decoded opaque credential to the same online redemption API;
neither path decides admission in the browser. The synthetic image under
`frontend/tests/fixtures/` exercises the fallback and has no live credential.

## Authentication imagery

The current split authentication shell uses an original code-drawn venue composition. No approved licensed event photograph is stored in this repository, and the supplied `inspo/` images are reference material rather than licensed product assets. A future photographic replacement must be stored locally with its source and license documented; unstable hotlinks and unlicensed reference images are not permitted.

## Responsive and accessibility rules

- The sidebar becomes a dismissible navigation sheet below 860px; the content sheet becomes the viewport.
- Tables collapse to labeled two-line records rather than horizontal miniatures.
- Inputs are at least 16px on mobile, touch targets at least 44px, and layouts reflow at 320px and 200% zoom.
- Focus uses a 2px visible outline with 3px offset. Status never relies on color alone.
- Motion is limited to direct interaction feedback and removed under `prefers-reduced-motion`.
- Long security values wrap at safe boundaries, remain selectable, and never overlap their container.

## Browser review artifacts

`frontend/tests/product-experience.spec.ts` attaches representative rendered
screens to Playwright's results: organizer at 1440px in light mode, platform at
1440px in dark mode, and gate at 390px in dark mode. Run
`npm run test:ui -- tests/product-experience.spec.ts` from `frontend/`, then
inspect the named PNGs under `docs/screenshots/`. These are clearly mocked browser
states; they demonstrate layout and interaction, not a verified live backend.
The same suite checks 320px reflow and automated WCAG 2.2 AA rules.
