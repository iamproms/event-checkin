# Privacy notice and participant import

Migration `0013_privacy_notice_workflow` adds draft, approval, and activation evidence to the existing tenant-scoped notice table. It does not seed a notice. It also records the organizer and time of each committed import authorization. Apply it with the migration owner after a database backup, before running the updated API.

## Platform administrator

Sign in with MFA and open **Platform Console → Organizations**. Search the organization directory by name, internal slug, or organizer email, then select **View details**. The detail panel shows the organization's UUID and a copy action. Select **Manage privacy notices** to open the notice screen with that organization selected. The Privacy notices screen also has a searchable organization selector; a `#privacy?organization=<UUID>` link opens the selected organization directly.

Create a draft with the exact approved notice text and recorded lawful basis. The text and basis become immutable immediately. Review the draft, enter an external approval reference, check the approval confirmation, and record approval. Then check the activation confirmation and activate the version. Only one version can be active per organization. A replacement notice creates a new version and does not rewrite prior registration evidence.

The directory endpoints are `GET /api/v1/platform/organizations?q=&limit=25&offset=0` and `GET /api/v1/platform/organizations/{tenant_id}`. Results contain organization metadata and the primary organizer email only where recorded by shared onboarding. Search and pagination are server-side, with a maximum page size of 100. No participant records are returned. The notice endpoints are `GET/POST /api/v1/platform/organizations/{tenant_id}/privacy-notices`, `POST /{version}/approve`, and `POST /{version}/activate`. They require an MFA-verified platform session and a current `tenant.provision` grant; mutations also require CSRF. The platform database role has tenant-scoped notice access through FORCE RLS and does not gain participant access. Drafting, approval, and activation are audited. An approval reference should identify the separately reviewed decision; clicking approval does not itself provide legal approval.

The **Test-only notice** option is accepted only in local/test environments. Never install synthetic text for real attendee data. A real release still requires approved notice text, lawful basis, data handling procedure, and transactional email approval.

## Organizer

Open **Participants → Bulk import**. Upload CSV or XLSX, map an email column and any required event questions, then select **Validate rows**. Name and phone are optional. Validation reports valid, invalid, and duplicate counts and does not create registrations. If the organization has no active approved notice, validation remains disabled with an instruction to contact a platform administrator. The backend also rejects validation if the notice is missing or its SHA-256 digest does not match.

After validation, review the counts and errors. Check the authorization statement, then choose **Import attendees**. The checkbox starts unchecked. The commit endpoint requires `authorization_confirmed: true`, revalidates the file and active notice, records actor/time in the import and audit log, and queues the existing idempotent background job. The worker rechecks the notice for each chunk. Each imported registration retains the approved notice version, digest, and lawful basis; attendee acknowledgement stays null and marketing opt-in stays false. Duplicate registrations are not overwritten.

The organizer endpoints are `GET /api/v1/events/{event_id}/imports/policy`, `POST /imports/preview`, `POST /imports/{import_id}/validate` with only column mapping, and `POST /imports/{import_id}/commit` with only the authorization boolean. Authorization remains tenant and event scoped.

## Release checks

- Rehearse migration upgrade and downgrade on an isolated test database. Downgrade refuses to discard notices or import confirmations created by this workflow.
- Run PostgreSQL privacy and import tests plus browser import tests. Use synthetic attendees and local mail capture.
- On the deployed host, confirm platform approval is inaccessible to organizers, the active notice is available to the intended tenant only, and CSV validation leaves registrations unchanged.
- Do not commit or send tickets to real attendees until the privacy notice, sender, provider, and import authority are approved.
