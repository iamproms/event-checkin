# Event Check-in Platform — Design System

**Status:** G-07 Quiet Precision foundation approved 2026-10-23; feature-level compositions and tenant brand bounds remain open.
**Working direction:** Quiet Precision.  
**Inputs:** PRD v1.0; [PRD review](PRD_REVIEW.md) and approved decisions D-01–D-13; [technical design](TECHNICAL_DESIGN.md); supplied wireframes; Taste Skill app guidance; Emil Kowalski design engineering guidance.  
**Visual companion:** [design foundations laboratory](design-system-preview.html). This iteration contains isolated specimens only; no application layouts or finished brand are proposed.

**Decision records:** [G-07 visual foundation](DECISIONS/G-07_VISUAL_FOUNDATION.md) and [G-08 event-first product experience](DECISIONS/G-08_EVENT_FIRST_PRODUCT_EXPERIENCE.md). Candidate comparisons below preserve the earlier design study. G-07 selects Inter, warm neutrals, deep evergreen, comfortable density, 4/8px radii, and neutral-fill navigation. G-08 changes only first-visit theme behavior to a three-state System/Light/Dark preference and establishes the framed-sheet operational composition. The documented typography, spacing, semantic-color separation, floating elevation, and reduced-motion rules remain the baseline. Alternative laboratory choices are historical specimens, not runtime options. [M0-02 state vocabulary v1](DECISIONS/M0-02_STATE_VOCABULARY_V1.md) governs feature adapters rather than visual primitives.

## 1. Direction and status

Quiet Precision combines precise hierarchy and useful density, clarity in controls and copy, and minimal structural chrome. Linear, Stripe, and Vercel are principles to study, not screen templates. Premium quality should come from type, spacing, alignment, subtle surface separation, and consistent interactions. The system should feel composed and confident during long admin sessions and brief gate actions.

**Approved product constraints remain fixed while visual choices are explored:** multi-tenant launch with branding and custom domains (D-01); online server-confirmed check-in and no offline acceptance (D-02); QR alone as entry evidence (D-03); personal or organizer-provided staff devices (D-04); one check-in per event/session for launch (D-05); self-service privacy operations and 90-day participant-detail expiry from event end with anonymous aggregates retained (D-06/D-11); launch messaging, billing, domains and PDF reports (D-07); FastAPI backend (D-09); independently unique required attendee email and phone per event (D-10); approved technical targets (D-12); Paystack subscriptions in NGN (D-13). Aesthetic choices below do not change these policies.

### Visual audit

| Before | After for review | Why |
|---|---|---|
| System UI with a fixed blue default, green and violet tenant examples | One self-hosted primary face, Inter or Geist; a neutral foundation with evergreen, slate blue, or graphite accent | Makes the chosen typography and accent visible without letting tenant examples define the platform brand. |
| 700-weight page titles, 32–48px preview headline, uppercase eyebrow | 400/500/600 hierarchy and restrained 28–32px specimen heading; no eyebrow | Hierarchy should come from scale, alignment, and whitespace rather than display treatment. |
| 8px controls, 12–14px cards, pill-like active navigation and status | Compare 4/8 and 6/10 radius pairs; active navigation uses neutral surface or a border/text treatment | Keeps geometry precise and avoids rounded chrome becoming the identity. |
| Shadows and nested cards across the preview | One surface step and a border; shadow reserved for genuine floating layers | Gives information density room and makes grouping structural. |
| Dashboard, scanner, registration mockups, then provisional layout sketches in the preview | Isolated specimens using identical content under each selected token set | Keeps this review on foundations and component craft. |
| Broad motion values and scanner demonstration in the preview | Instant token switching; no decorative motion in the laboratory | The comparison should not be distorted by transitions; repeated operational feedback stays immediate. |
| Contrast readout parsed hex tokens as decimal fragments | Parse six-digit hex and RGB values explicitly; show text, action, border and semantic pairs | The previous numeric readout was unreliable even when the palette values themselves were sound. |
| Font files existed but loading was inferred from file presence | Preload both faces through the browser FontFaceSet and report loaded or fallback status | Lets the reviewer see whether this browser actually loaded each face. |
| A few type sizes and four button examples | Full type/spacing scales and explicit control states | Exposes rhythm, legibility, and component gaps before any screen design. |

This audit applies the Taste Skill's app principles of quiet borders, restrained color in chrome, flat surfaces, honest status and dense substance. Emil's guidance favors purpose-specific motion, fast frequent actions, pointer-aware hover, and explicit focus/pressed behavior. Neither skill substitutes for checking real venue devices and accessibility during implementation.

## 2. Foundation values and historical candidates

The laboratory retains independent controls for historical comparison. G-07 approves its Inter, warm-neutral, light, deep-evergreen, comfortable, precise 4/8, neutral-fill combination. Other combinations remain design-study examples. Tenant-selected accents require separate validation and approval before use.

### Typography

| Candidate | Character and likely fit | Watch point |
|---|---|---|
| Inter | Familiar, open forms and reliable reading in dense data and forms | May feel generic unless hierarchy and spacing are carefully resolved. |
| Geist | Tighter, crisp character that may suit concise navigation and status | The bundled Geist preview file covers Latin characters only; check Nigerian names, diacritics, numerals, and international text with the intended production font package and fallback. |

Production UI uses self-hosted **Inter** at weights 400, 500, and 600 with a system sans-serif fallback. The historical HTML compares both Inter and Geist and reports browser font-load status. Font metadata confirms the bundled Inter asset includes `Ọ`, `ẹ`, and `₦`; broader script coverage still needs testing in the target browsers.

| Type token | Size / line height | Weight | Intended use |
|---|---:|---:|---|
| `type.display` | 32 / 40 px | 600 | Rare top-level summary, not routine chrome. |
| `type.page` | 28 / 36 px | 600 | Page title. |
| `type.subsection` | 24 / 32 px | 600 | Major content group when needed. |
| `type.section` | 20 / 28 px | 600 | Standard section heading. |
| `type.component` | 16 / 24 px | 500–600 | Component title. |
| `type.body` | 15 / 24 px | 400 | Operational prose and form content. |
| `type.support` | 14 / 20 px | 400 | Instructions and secondary copy. |
| `type.label` | 14 / 20 px | 500 | Field and control labels. |
| `type.caption` | 13 / 18 px | 400 | Nonessential metadata only. |

Use tabular numerals for live counts and financial values, with explicit `₦` and thousands separators. Use monospace only for technical strings. Do not tighten body letter spacing. Long names, domains, and email addresses wrap or expose the full value. The laboratory includes Nigerian names, diacritics, long strings, amounts, and privacy-sensitive administrative copy; confirm font shaping and fallback in a rendered browser before approval.

### Neutral and accent palettes

The preview compares **warm neutral** and **neutral gray** foundations in both light and dark modes. The former makes large quiet surfaces slightly softer; the latter is more austere. Both use a single modest surface step. Candidate accents are **deep evergreen**, **slate blue**, and **graphite**. Accent is for the primary action, link, selected control, and limited key data emphasis. It is not a substitute for semantic success/warning/error colors.

Production UI uses the **warm-neutral** and **deep-evergreen** columns. The theme preference is System, Light or Dark. System is the first-visit value, resolves from `prefers-color-scheme`, and follows later operating-system changes. Explicit Light or Dark selections persist in same-origin local storage. Both resolved themes must be tested with the same content and interaction states. Future tenant branding may change only approved action branding after contrast validation; it cannot alter semantic status, focus, critical scan outcomes, or accessibility rules.

| Role | Warm light | Neutral light | Warm dark | Neutral dark |
|---|---|---|---|---|
| Canvas | `#F7F6F3` | `#F7F8FA` | `#171816` | `#15171A` |
| Surface | `#FFFFFF` | `#FFFFFF` | `#21231F` | `#202328` |
| Quiet surface | `#F1F0EC` | `#F1F3F5` | `#292C27` | `#292D33` |
| Primary text | `#20231F` | `#20242A` | `#F4F4F1` | `#F4F6F8` |
| Secondary text | `#555B54` | `#57606B` | `#C2C8BE` | `#C4CBD3` |
| Hairline border | `#D9DCD5` | `#D8DDE3` | `#434942` | `#444B55` |
| Control border | `#777F74` | `#78818C` | `#8C958A` | `#929BA6` |

| Accent | Light action fill | Dark action fill | Use hypothesis |
|---|---|---|---|
| Deep evergreen | `#205B4A` | `#A6D7C5` | Most distinct from neutral chrome; check distinction from semantic success. |
| Slate blue | `#355B83` | `#A9C8EC` | Familiar action cue; check that it stays restrained across large areas. |
| Graphite | `#303A43` | `#C8D0D7` | Maximum restraint; check that primary action and selection remain findable. |

Use white text on light accent fills and `#111817` on dark accent fills in the specimen. Quiet selected surfaces remain neutral so accent is not spread through every row. Visible focus uses a solid outline with offset. The preview's programmatic contrast table reports the selected combination, but the full light/dark, neutral/accent matrix and later tenant overrides still require review on rendered UI.

**Semantic colors are independent of the accent.** M1-05 baseline status pairs: light success `#2C6532` on `#EBF5E9`; warning `#714B0B` on `#FCF2DC`; danger `#8D2630` on `#FCEBED`; information `#334E68` on `#EAF1F7`. Dark success `#D8F1D0` on `#283B28`; warning `#FFE8BB` on `#473516`; danger `#FFDADF` on `#4B252B`; information `#D8EAF8` on `#273B4D`. Measured text/background ratios range from 6.23:1 to 10.22:1 across these pairs. Success is greener than the evergreen action accent, uses a pale/opaque status field rather than a solid action fill, and always says what happened. The distinction is semantic and structural as well as chromatic; color alone never carries the decision. The same status roles serve scanner results and other critical feedback. Tenant accents never recolor them.

### Spacing, shape, density

| Choice | Comfortable | Compact | Review criterion |
|---|---:|---:|---|
| Base rhythm | 4px steps; 8px main rhythm | Same tokens | Alignment stays consistent across modes. |
| Control height | 44px | 38px in admin data work only | Compact mode must not shrink gate actions or touch-critical controls. |
| Control horizontal padding | 14px | 11px | Labels remain legible and do not crowd focus. |
| Row height | 44px | 36px in pointer/keyboard-heavy tables | Truncation and targets need contextual checks. |
| Section gap | 32px | 24px | Information density without card nesting. |
| Surface inset | 20px | 16px | Borders and spacing establish groups. |

Radius option **precise**: controls 4px, surfaces 8px. Radius option **softened**: controls 6px, surfaces 10px. Neither is a pill. Use flat 1px borders; reserve a shadow for a popover, menu, or dialog only when needed to distinguish a floating layer. A control border must remain visible; a hairline divider may be quieter. Major shell widths and breakpoints remain content-driven and need screen design review after foundation approval.

Complete spacing scale: `space.1=4`, `.2=8`, `.3=12`, `.4=16`, `.6=24`, `.8=32`, `.12=48`, `.16=64` px. Use 4–8px within a control, 12–16px between close peers, 24–32px between component groups, and 48–64px only between major content regions. The preview renders each measured gap. Comfortable is the recommended starting mode; compact remains a contextual option for dense desktop administration, not a global shrink setting.

### Component treatment comparison

| Element | Candidate treatment | What to inspect |
|---|---|---|
| Primary action | Solid accent fill, restrained radius, 600 label | Does it stand out in both graphite and color accents? |
| Secondary action | Surface fill with control border | Is it distinct from a plain field? |
| Tertiary action | Text action with clear underline or equivalent affordance | Is it discoverable without competing with primary? |
| Destructive action | Independent danger fill and explicit verb/object | Is destructive intent clear in both themes? |
| Input | Persistent label, clear border, hint/error below | Are border, focus, and error visible in both themes? |
| Navigation item | Text plus neutral selected background or slim border | Is selection clear without a colored pill or badge? |
| Status | Tinted semantic surface, explicit heading and short instruction | Does status remain legible without relying on hue? |
| Grouped content | One rule or one surface step | Does hierarchy hold without nested cards? |

The laboratory uses the same labels, copy, and specimen order for every candidate combination. Switching controls changes only the selected foundation tokens, which helps isolate the design decision.

**State contract:** default, fine-pointer hover, pointer press, keyboard focus, disabled, loading, selected and validation error are shown as isolated specimens. Focus is a 2px outline with 3px offset. Press uses only a subtle transform and only on fine-pointer interaction; keyboard selection stays immediate. Loading retains the action label's meaning and focus, uses `aria-busy`/`aria-disabled`, blocks duplicate submission in the eventual application handler, and is expressed in text without an indeterminate decorative animation. Disabled controls need a reason nearby in real workflows. Validation errors use a field border, `aria-invalid`, associated text, and a recovery instruction. Selected navigation is indicated by neutral fill and weight, with `aria-current`; accent-rule remains a comparison option.

### Icons, elevation and motion

Use one outline icon set. Candidate sizes: 14px inline cue, 16px navigation/action adjunct, 20px touch action. Candidate strokes: 1.5px at 14–16px, 1.75px at 20px. Icons are subordinate to labels, use current text color, and have accessible names when they are the sole affordance. Do not place routine icons in tinted discs or use an icon where a word is clearer. Status must still have text.

Base and grouped surfaces have **no shadow**. A floating menu/popover may use `0 8px 24px rgb(25 30 25 / 12%)` in light mode; dark mode may use `0 12px 28px rgb(0 0 0 / 38%)`. A floating shadow is paired with a surface fill and no competing border. Dialogs may need a stronger scrim/edge separation after actual screen review. Elevation never communicates status by itself.

| Motion token | Provisional value | Purpose and limit |
|---|---|---|
| `motion.instant` | 0ms | Scanner result, keyboard command, repeated selection, validation message. |
| `motion.press` | 120ms, `transform: scale(.97)`, `cubic-bezier(.23,1,.32,1)` | Fine-pointer press acknowledgement only; release snaps back. |
| `motion.overlay.enter` | 180–220ms, opacity and transform, same ease-out | Occasional menu/drawer spatial continuity; no layout animation. |
| `motion.overlay.exit` | 140–180ms, opacity and transform | Shorter exit; interruption must remain possible. |

The preview implements only pointer press feedback; overlay tokens are documentation, not animation added to the sheet. `prefers-reduced-motion` removes press scale and future spatial translation. No `transition: all`, shimmer, bounce, stagger, scanner celebration, or motion required to understand a state. This follows Emil's frequency, purpose, performance and reduced-motion guidance.

## 3. Functional interaction contracts retained from the prior design review

- Check-in success appears **only** after a committed server response. A timeout or disconnect says confirmation is unavailable and keeps the same retry context; it never appears green (D-02). Scanner result wording distinguishes ready, reading, verifying, accepted, duplicate, invalid/revoked, event closed, cannot confirm, and camera unavailable. QR alone suffices (D-03); participant identity is not shown to gate staff by default. Personal and organizer-provided devices are both supported (D-04).
- The overview uses confirmed registered/checked-in/remaining values, shows freshness and stream state, and never presents a pending offline queue. A missing query is not zero. After 90 days from event end, participant detail is unavailable but anonymous aggregates remain (D-06/D-11).
- Participant import previews duplicate email and duplicate phone as separate errors (D-10). Export, ticket reissue, individual participant deletion, and whole-event participant-data deletion use explicit scope and consequence copy. No silent overwrite or promised undo.
- Messaging separates recipient eligibility, consent, channel, preview, send confirmation, provider acceptance, delivered, failed, and unknown. Reports distinguish participant detail from retained anonymous aggregates. Paystack subscriptions are displayed in NGN; prices and plan terms remain open (D-07/D-13).
- Domain setup distinguishes ownership, DNS, TLS, and activation states. White-label settings validate logo assets and accent contrast in both themes; tenant accent never replaces semantic status colors. Sender verification is separate from web-domain activation.
- Public registration includes required name, email, phone, configured fields, privacy notice, and any required channel consent. Unauthenticated duplicate feedback avoids contact enumeration; authenticated admins can see field-specific validation. Tickets do not put personal details into the QR payload.
- Actions use clear verbs. Destructive actions state scope and consequence. Check-in, payment, campaign send, domain activation, and deletion wait for server confirmation. Persistent failures appear inline, not only in a disappearing toast.

## 4. Accessibility and responsive constraints

Target WCAG 2.2 AA. Normal text requires at least 4.5:1 contrast, meaningful non-text boundaries/status graphics at least 3:1, and target sizing must meet WCAG 2.2's 24px minimum or spacing exception. Primary scanner actions target at least 44 × 44px. [WCAG 2.2](https://www.w3.org/TR/WCAG22/), [text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum), [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html), [target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum).

Use visible keyboard focus, semantic headings, persistent labels, associated errors, and text status. Announce scanner results once per decision, not on every camera decode. Support 200% zoom, 320px viewport reflow, portrait/landscape, screen cutouts, larger text, reduced motion, and non-Latin names. Keep event time zones explicit; store UTC timestamps in the backend. Copy and formats must be localizable. Comfortable and compact density never override accessibility for high-pressure touch actions.

Emil's interaction guidance applies by task frequency: frequent scanner and keyboard feedback is immediate; any later overlay motion needs a specific purpose, property, duration, interruption path, and reduced-motion behavior. Hover styling is only for fine pointers. The foundation laboratory has only the documented pointer-press transition; token switching is instant.

## 5. Remaining decisions and review evidence

**Foundation approved by G-07 and amended by G-08:** Inter, warm neutral, System/Light/Dark preference, evergreen, comfortable with limited compact admin use, 4/8 radii, neutral-fill navigation, documented scale, semantic separation, and restrained elevation/motion. G-08 owns the framed-sheet application composition and event-first operational priority. **Still open:** final licensed authentication photography, tenant accent bounds and platform attribution, browser/device support matrix, venue connectivity escalation wording, aggregate privacy threshold, campaign consent language, and subscription plan terms. This document does not silently settle them.

**Review criteria:** compare the same specimen content at 100% and 200% zoom; try keyboard controls and both themes; inspect long names, numbers, error text, and status distinction; compare accents in light and dark with both neutral foundations. The HTML has only isolated specimens. Its controls are a review aid, not a runtime design-system implementation.

**Evidence and limits:** local font files are bundled with [Inter](assets/fonts/INTER-OFL.txt) and [Geist](assets/fonts/GEIST-OFL.txt) license copies and identified by font metadata. The preview checks browser font-load status at runtime. Contrast calculations were corrected to parse hex tokens. Calculated ratios across the tested light/dark palette include primary text/canvas 14.67–16.58:1, secondary text/surface 6.38–9.63:1, action text/fill 7.06–11.59:1, revised semantic text/surface 6.23–10.22:1, destructive text/fill 8.56–13.78:1, and control boundary/surface 3.95–5.60:1. Hairline separators are quieter and cannot carry essential meaning. Static inspection found local assets, unique IDs, associated form labels, balanced CSS braces, and valid embedded JavaScript. A DOM interaction check switched all **96** font/neutral/theme/accent/density/radius combinations; each selector retained its `aria-pressed` state and every contrast readout remained numeric. This DOM check does not render pixels or load fonts. The current sandbox exposes no browser tab and blocks headless Chrome, Firefox and Playwright Chromium, so no screenshot or actual browser font-rendering claim is possible from this run. Final typography fit, anti-aliasing, 320px and 200% zoom reflow, focus appearance, keyboard operation, and assistive-technology behavior require rendered browser/device review. Every tenant-selected palette must be validated before publication. This historical laboratory evidence does not replace rendered M1-05 production validation.

**M1-05 implementation evidence:** The Fedora Chromium suite passed 10/10 isolated-component and migrated-auth browser tests, including actual Inter loading, 320px reflow with doubled root text, both themes, keyboard dialog focus, axe checks, contrast, and selected rendered-pixel/geometry assertions. This does not constitute a manual screen-reader review or an actual browser 200% zoom check; those remain release-readiness checks. The historical laboratory's alternative palettes are outside the approved production combination.

## 6. Traceability

| Source | Preserved design response |
|---|---|
| F-01/F-13; D-01/D-07/D-13 | Multi-tenant brand/domain settings and Paystack NGN billing states. |
| F-04; D-10 | Required unique attendee email and phone, with distinct private/admin error handling. |
| F-07; D-02–D-05 | Online, QR-only, single-session gate decisions on personal or organizer devices. |
| F-09/F-12; D-02 | Confirmed live dashboard with freshness and no offline pending count. |
| F-10/F-11; D-07 | Messaging and PDF/CSV reports with job and delivery states. |
| N-01/N-05; D-06/D-11 | Accessible flows, self-service privacy controls, and 90-day participant-detail expiry. |
