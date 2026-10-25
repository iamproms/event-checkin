# M2-04 — Tenant branding contract

**Decision authority:** Product-owner G-07 addendum, 2026-10-24. Tenant-selected colors are permitted only after measured contrast on their actual light and dark surfaces. Semantic and focus colors remain platform-controlled.

## Versioned workflow

Only an active tenant owner or administrator with `tenant.settings` and completed MFA may edit branding. A draft has a revision number. Saving with a stale revision returns 409; a tenant row lock serializes publish and restore. Publishing copies the validated draft to an immutable, numbered version and updates the current published pointer in one transaction. Restoring a historical version creates a new numbered version and updates the draft; history remains intact. Draft, logo, publish, and restore actions include the actor in tenant-scoped audit records. Sender display name is presentation only and does not verify a sender domain or authorize production email.

The current `tenant_branding` row is the published view. `tenant_branding_drafts`, `tenant_branding_versions`, and `tenant_branding_audit` use FORCE RLS and restricted runtime grants. The runtime role still cannot read the global `tenants` table: a security-definer helper returns only the active tenant ID/name selected by the transaction's established tenant context, and branding writes serialize through a tenant-derived advisory lock. No platform administration role gains tenant branding or participant-table access.

## Logo handling

The admin uploads PNG, JPEG, or WebP to `PUT /api/v1/branding/logo` as a binary request body with CSRF protection. The API caps streamed bytes at 2 MiB, confirms the declared MIME matches decoded content, rejects animation and dimensions outside 64–2048 pixels, and re-encodes one frame as PNG to strip metadata. SVG is unsupported, including active SVG content. The sanitized PNG is stored in the existing private S3-compatible bucket under a random `retained/tenants/{tenant}/branding` key and tracked in `private_objects` with purpose `branding_logo`. The retained prefix is deliberately outside M1-04's one-day local orphan rule. The public logo endpoint reads **only** the current published object after active host resolution; the draft preview endpoint requires tenant authorization. Neither endpoint returns a storage URL or accepts an object key. Historical objects remain private so published versions can be restored. Cleanup of abandoned draft objects is an operational follow-up.

## Color and UI constraints

Colors are six-digit `#RRGGBB`. Primary and accent must have at least 3:1 contrast against both `#ffffff` light surface and `#21231f` dark surface. The server selects black or white action text and requires at least 4.5:1 contrast against the primary fill. A rejected color returns an actionable 422 message. The public client may apply only action fill/text and accent decoration; status colors, focus indicators, and destructive actions stay platform-owned. The branding editor previews both themes and uses the M1-05 components.

## API

All administrative writes require the existing tenant session, `tenant.settings`, and CSRF token. JSON bodies reject unknown fields.

| Endpoint | Result |
| --- | --- |
| `GET /api/v1/branding/draft` | Draft fields, revision, published version, and authorized draft logo path. |
| `PUT /api/v1/branding/draft` | Save fields with `revision`, `display_name`, colors, and `sender_name`. |
| `PUT /api/v1/branding/logo` | Validate, privately store, and attach a logo to the draft. |
| `DELETE /api/v1/branding/logo` | Remove the logo from the draft; published versions remain unchanged. |
| `POST /api/v1/branding/publish` | Publish the saved `revision`. |
| `POST /api/v1/branding/restore/{version}` | Publish a new version copied from historical content. |
| `GET /api/v1/branding/history` | Last 50 published versions and attributable change events. |
| `GET /api/v1/branding/public` | Host-resolved published display name, colors, sender display name and logo path. |
| `GET /api/v1/branding/public/logo` | Sanitized published PNG, served from private storage only after host resolution. |

`/public` applies no draft data. Unknown or unsafe hosts fail through M2-01 authority checks. Branding cannot authorize sender-domain use, participant reads, or ticket delivery.

## Activation limits

Real custom-host staging remains gated by G-06 edge/DNS/TLS approval. Production object-storage provider and data region require G-06 approval. Production transactional mail and sender-domain verification require G-04/G-06 approval. This contract supports local and controlled staging adapters without implying those providers are selected.
