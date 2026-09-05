# Owner-scoped telemetry platform

## Data and ownership

Every telemetry event and import job carries the authenticated user's `user_id`. `organization_id` is nullable and reserved for a later organization-tenancy design. Personal Overview, Usage, Costs, Models, history, reset, and import endpoints always add a server-side owner predicate; browser-supplied ownership is never accepted. Administrators use the same personal scope unless an explicitly administrative aggregate endpoint is used.

Telemetry stores timestamp, provider, model, application, input/output/total tokens, recorded cost, latency, bounded metadata, source, import reference, and creation time. Compound indexes cover the owner/time, owner/model, owner/provider, and owner/application query patterns. Import jobs index owner/status and owner/creation time.

## Import workflow

1. `POST /api/v1/import/start` validates metadata and creates an owned job.
2. `POST /api/v1/import/{id}/upload` streams multipart data in 1 MB reads to a random server-controlled path.
3. `POST /api/v1/import/{id}/analyze` streams CSV, JSON arrays, or JSONL, detects encoding/delimiter, samples bounded values, and suggests aliases.
4. The user reviews or changes the mapping.
5. `POST /api/v1/import/{id}/commit` reparses, validates, stages and flushes rows, verifies a nonzero insertion count, and commits atomically.
6. Status, rejected examples, and owner-scoped history remain queryable. Temporary data is removed after completion, failure, cancellation, or reset.

Required mapped fields are application, provider, and model. Common desktop aliases such as `prompt_tokens`, `completion_tokens`, `vendor`, `model_name`, `total_cost`, and `latency` are preserved. Invalid rows are counted with at most 100 safe error examples. An all-rejected import becomes `FAILED`; it cannot report false completion.

## Limits and safety

- Dedicated imports: 500 MB maximum; ordinary JSON APIs retain their schema-level bounds.
- Three active jobs per user.
- Source filename is metadata only and cannot contain paths; storage uses a random identifier.
- Individual JSONL/JSON records and CSV fields are limited to 2 MB.
- Duplicate upload and incomplete/oversized upload are rejected.
- State-changing routes require the session-bound CSRF token.
- Raw telemetry is never written to audit events.

The current commit operation runs synchronously. A background worker with durable cancellation checkpoints is the recommended next scaling step before multi-gigabyte or highly concurrent ingestion.

## Analytics and reset

Usage, Costs, and Models use SQL aggregation rather than loading events into Python. `DELETE /api/v1/telemetry` removes only the caller's telemetry and import records, cleans remaining temporary files, and emits a safe audit count.

## Next phase

After PostgreSQL runtime/load validation, migrate budgets and pricing provenance, then forecasting and optimization. Preserve owner predicates and parity fixtures for each addition.
