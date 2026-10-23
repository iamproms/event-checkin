# M1-04 reliable jobs and private file decisions

**Status:** Approved by product owner, 2026-10-23. Applies to M1-04 only.

## D1 — Job contract

PostgreSQL is authoritative. A business transaction persists its change, job and outbox event atomically. Jobs move through `pending`, `running`, `succeeded`, `retry_wait`, and `dead`. Attempts are bounded (five by default, configurable by job type), with exponential backoff and jitter, leases, safe error codes, timestamps and numeric progress. A lease may expire and be reclaimed after a process crash. Queue delivery is at least once; handlers must be idempotent. External destinations require their own idempotency key or an explicit limitation. Dead-letter inspection/retry is operator-only. There is no public general job submission endpoint.

## D2 — Private file contract

Provide a reusable private storage interface, tenant-isolated metadata, authorization, signed URLs and cleanup hooks. No generic production upload or download API is approved. `internal_test_artifact` exists only in local/test environments and may contain synthetic non-personal data only. It accepts `text/plain` or `application/pdf`, at most 5 MiB, with access only by the test harness and authorized internal test operations. Its maximum retention is 24 hours and it is disabled in production. Real purposes and permissions require approval in their owning milestones.

## D3 — Provider boundary

Local integration tests use Redis and S3-compatible object storage. Production provider, region, credentials and operational policy remain open under G-06. Signed URL lifetimes are configurable, initially five minutes for downloads and ten minutes for uploads. Server-side authorization, size/type limits, expiry and lifecycle cleanup are required.

These decisions do not activate M2/M3/M4/M5 business workflows or weaken M1-02 RLS and M1-03 authentication.
