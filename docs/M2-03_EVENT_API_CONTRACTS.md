# M2-03 event API contracts

All paths use `/api/v1/events`, the trusted tenant hostname, and a valid tenant session. Mutations require the existing `/api/v1/auth/csrf` cookie/header contract. Responses are `no-store`. A tenant ID in a URL or request body has no authority. Event IDs are checked against the authorized tenant under FORCE RLS.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | List up to 200 authorized events, newest start first |
| POST | `/` | Create draft with slug, name, IANA zone, offset-bearing start/end, optional location |
| GET | `/{event_id}` | Retrieve authorized configuration |
| PUT | `/{event_id}` | Edit with `revision`; draft schedule/window changes or published name/location |
| PUT | `/{event_id}/form` | Create a new immutable draft form version with `revision`, `form_schema` |
| GET | `/{event_id}/readiness` | `{ready,instructions}` |
| POST | `/{event_id}/transitions/publish` | Publish ready draft with `revision` |
| POST | `/{event_id}/transitions/close` | Close published event with `revision` |
| POST | `/{event_id}/transitions/cancel` | Terminal cancellation with `revision` |
| GET | `/{event_id}/gates` | List event gates |
| POST | `/{event_id}/gates` | Create gate with `name,enabled` |
| PUT | `/{event_id}/gates/{gate_id}` | Rename/enable/disable gate |

The event response includes `id,slug,name,status,revision,starts_at,ends_at,timezone,location,registration_opens_at,registration_closes_at,checkin_opens_at,checkin_closes_at,form_schema,form_schema_version,pii_purge_due_at`. Gate responses include `id,event_id,name,enabled`. Normal timestamps are UTC ISO 8601; API clients must supply explicit offsets. Empty optional windows are `null`.

The organizer UI accepts local date/time in the selected event zone and converts unique times to UTC. It rejects skipped and repeated daylight-saving wall times rather than guessing which instant the operator meant. The API can still receive an explicit offset for an ambiguous instant.

Custom form schema v1 is `{"fields":[{"key":"meal","label":"Meal preference","type":"select","required":false,"options":["Vegan","Other"]}]}`. Types: `text`, `textarea`, `select`, `checkbox`. Keys are unique lowercase identifiers; built-in `full_name`, `email`, `phone` are reserved. Maximum 30 fields and 30 select options. Unknown properties and angle-bracket markup in labels/options are rejected; values are rendered as text by the UI. No answers or participant data are exposed here.

Errors use FastAPI `detail: {code,message}`: `AUTH_DENIED` 401, `FORBIDDEN` 403, `EVENT_CONFLICT` 409, `EVENT_INVALID` 422. A stale revision or duplicate slug/gate produces 409. Database row locking serializes concurrent edits and transitions.

Tenant owner/admin can create and manage all own events. Organizer/manager require an active assignment for an existing event; they cannot create an unassigned event. Gate supervisors may edit only assigned gates through the existing `gate.manage` permission. Gate scanners cannot use event configuration APIs. Staff invitations remain at `POST /api/v1/auth/invitations`; M2-03 validates that a target event is draft/published and its optional gate is active and belongs to the same tenant/event. This is the v1 staff-assignment hook; there is no separate assignment management UI.
