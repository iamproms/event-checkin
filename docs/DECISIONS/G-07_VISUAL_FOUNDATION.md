# G-07 — Quiet Precision visual foundation

**Status:** Approved by product owner, 2026-10-23.

**Applies to:** M1-05 shared UI foundations and later production interfaces.
**Source:** Product-owner M1-05 implementation authorization.

## Approved foundation

- Self-hosted Inter with a system sans-serif fallback. Use weights 400, 500, and 600.
- Warm-neutral surfaces; light is the default. Dark mode is fully supported and selected explicitly. Persist the user's selection locally. Do not switch automatically from OS preference alone.
- Deep evergreen for primary actions. Semantic status colors and focus indicators are independent of tenant branding.
- Comfortable density by default. Compact density is limited to suitable admin interfaces and never shrinks touch-critical controls.
- 4px control radii, 8px surface radii, the documented 4px-based spacing scale, neutral-fill selected navigation, subtle elevation on floating surfaces only, and reduced-motion support.
- Tenant branding cannot override semantic colors, focus indicators, critical scan outcomes, or accessibility rules. Every tenant color combination requires measured contrast validation before publication.

The initial token values and typography scale are recorded in [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md). The prior comparison laboratory remains historical review evidence, not a runtime theme picker.

## M2-04 tenant-brand bounds

Tenant primary and accent colors use six-digit sRGB hex values. Each published color must have at least 3:1 contrast against the actual approved light and dark surfaces. Primary-action text is selected from the approved light/dark text pair and must reach 4.5:1 against the primary fill. Accent is used only for non-text boundaries and restrained identity details. Tenant colors never replace semantic success, warning, danger, focus, scanner-result, or body-text tokens. The branding editor previews both themes, but the backend repeats the checks and is authoritative.

Logos are raster-only PNG/JPEG/WebP inputs, decoded and re-encoded as metadata-free PNG. SVG and animated content are intentionally unsupported.

## Still feature-level decisions

Scanner device/browser support, scanner result copy, platform navigation layouts, and later production screen compositions require decisions in their owning milestones. M1-05 supplies accessible primitives; M2-04 owns the brand validation contract above.
