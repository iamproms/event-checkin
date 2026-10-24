# M2-03 local operation and migration

1. Start the existing local stack without deleting volumes: `docker compose up -d db redis object-storage`. Apply roles with the existing local-role procedure, then run `docker compose run --rm migrate` from this branch.
2. Serve the FastAPI app with restricted runtime and identity logins. The organizer interface is `/events.html` on an active tenant hostname. It uses the existing M1-03 secure cookie and CSRF flow.
3. Create a draft, configure registration and one check-in window in the event's named time zone, add the form questions and an enabled gate, inspect readiness, then publish. The UI converts unique local times to UTC; API clients supply an explicit offset. Close or cancel through the confirmation action. Cancellation and closure cannot reopen.
4. Inspect `event_config_audit` with an authorized tenant-scoped transaction when investigating a change. It stores actor IDs, event IDs, action and safe version/gate IDs, not participant fields.
5. For conflicting edits, reload the event and compare revision before retrying. For a duplicate slug or gate name, choose another value. A published schedule correction or reopening requires a later approved policy; direct SQL changes are not an operator workaround.

Revision `0007_event_configuration` extends existing event/gate tables, backfills form version snapshots for existing events, adds composite registration/form-version integrity, FORCE RLS on snapshots and audit, and database lifecycle guards. Upgrade is non-destructive. Downgrade on a populated event/registration database deliberately fails pending a reviewed migration plan; downgrade is tested only in an isolated empty database.

The 90-day UTC deadline is persisted and recalculated; the actual participant purge job remains M5-03. M2-02 billing was reprioritized for the demo-critical path and remains incomplete. This local workflow does not demonstrate an approved staging domain, production edge, production email, or production password corpus.
