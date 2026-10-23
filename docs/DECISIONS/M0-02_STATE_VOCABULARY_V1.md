# M0-02 — State vocabulary, version 1

**Status:** Approved mapping approach; this version records only states already named in project contracts.

**Authority:** Product-owner M1-05 decision; D-02 online-only check-in; [M1-04 job contract](M1-04_JOBS_FILES.md); [M1-03 auth contract](../M1-03_AUTH_CONTRACTS.md).
**Rule:** Domain state → user-facing label → semantic tone → required instruction. The mapping is performed by feature adapters, never by presentation primitives. Wording below is a UI proposal for review; it does not create backend identifiers or API behavior.

| Documented outcome/state | User-facing label | Semantic tone | Required instruction |
|---|---|---|---|
| Scan: ready | Ready to scan | Information | Present a QR code. |
| Scan: reading | Reading code | Information | Hold the code steady. |
| Scan: verifying | Verifying | Information | Wait for server confirmation. |
| Scan: accepted | Entry confirmed | Success | Admit the ticket holder. Show only after a committed server response. |
| Scan: duplicate | Already checked in | Warning | Do not admit a second time; seek a supervisor if needed. |
| Scan: invalid or revoked | Ticket not valid | Danger | Do not admit; seek a supervisor. |
| Scan: event closed | Check-in closed | Warning | Do not admit; contact an organizer. |
| Scan: cannot confirm | Could not confirm | Warning | Keep the same retry context and retry when connected; never imply entry. |
| Scan: camera unavailable | Camera unavailable | Warning | Check camera permission or use an approved device. |
| Job `pending` | Waiting | Information | No action required. |
| Job `running` | In progress | Information | Check progress later. |
| Job `retry_wait` | Retrying | Warning | Check progress later; operator action may be needed if retries exhaust. |
| Job `succeeded` | Complete | Success | Continue to the result when authorized. |
| Job `dead` | Needs operator review | Danger | Contact an authorized operator; retry is operator-only. |

The scanner entries are conceptual states from the approved design documents; the scan API and its exact identifiers belong to M4. A **rejection** is a server-confirmed denial such as invalid, revoked, or event closed. It is distinct from accepted, duplicate, and cannot-confirm. Cannot-confirm is never a rejection or an acceptance: the server decision is unknown to the client. The M1-04 job identifiers above are implemented PostgreSQL values. No offline success or pending-sync state exists at launch. Future payment, domain, campaign, and registration vocabularies require their own reviewed contract versions; this document does not assign their backend codes.
