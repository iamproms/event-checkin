# G-01 — Event configuration contract, version 1

**Status:** Approved product-owner decisions for M2-03, 2026-10-24. Other G-01 topics remain open.

- Event states are `draft`, `published`, `closed`, and `cancelled`. Allowed transitions: draft → published/cancelled; published → closed/cancelled. Cancellation is terminal; closed events do not reopen in v1.
- Each event has exactly one configured check-in window. Registration has explicit opening and closing timestamps.
- Event time zones use IANA names. API timestamps require an explicit offset and persist as UTC instants. Ambiguous local DST wall times must be disambiguated by their supplied offset. The UI does not guess an offset from the operator's device.
- Registration form schemas have monotonically increasing integer versions. Every snapshot is append-only; publishing freezes the selected version. Registrations later reference an existing version by composite tenant/event/version key.
- Gates belong to one tenant/event pair. A gate may be enabled or disabled. Staff assignment follows the existing G-02 invitation and composite assignment contract.
- Privileged event, form, gate and lifecycle changes are attributable and audited.
- The personal-data purge deadline is exactly 90 × 24 hours after the event end UTC instant. Changing a draft event end recalculates the deadline. Execution of the purge belongs to M5-03 and its remaining G-06 privacy decisions.

**M2-03 engineering bounds:** Draft schedules and forms can change. A published schedule and form version are fixed; name/location and gate configuration may change until closure/cancellation. A new form version after publication, registration correction, on-site registration, reporting metric definitions, and reopening require later product decisions. Publishing requires explicit registration and check-in windows, a valid form snapshot, an enabled gate, and a future event end.

These bounds do not activate participant registration, ticket issuance, scanning, billing, or the retention worker.

## M0-02 event-state vocabulary, version 1

The feature adapter maps each approved domain state to a label, semantic tone and next instruction. Presentation primitives do not infer event state.

| State | Label | Tone | Instruction |
|---|---|---|---|
| `draft` | Draft | Information | Complete setup and review readiness before publishing. |
| `published` | Published | Success | The published schedule and form are fixed. |
| `closed` | Closed | Warning | This event cannot reopen in v1. |
| `cancelled` | Cancelled | Danger | Cancellation is final. This event cannot reopen. |
