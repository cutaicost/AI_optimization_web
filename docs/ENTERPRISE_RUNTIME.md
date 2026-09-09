# Enterprise runtime

## Topology

The Compose development topology contains `web`, `api`, `worker`, and PostgreSQL 17 with persistent storage and health-gated dependencies. PostgreSQL credentials and the session secret must be supplied through environment variables; Compose contains no password defaults. The API applies Alembic migrations before serving. The worker begins only after API health succeeds.

For lightweight development and tests, omit `DATABASE_URL` to use SQLite. For PostgreSQL, set a SQLAlchemy psycopg URL such as `postgresql+psycopg://...`. SQLite support is retained but PostgreSQL is the concurrent enterprise target.

## Workers, heartbeats, and leases

Each dedicated worker registers a safe ID, hostname, version, start time, state, current job, and heartbeat. Heartbeats run every 15 seconds and renew a 90-second job lease. States are `STARTING`, `IDLE`, `BUSY`, `STOPPING`, and `OFFLINE`. No environment values or credentials are stored.

Lease renewal is tied to completed import batches, not merely to a live heartbeat. If a dedicated worker makes no progress for three heartbeat intervals, it stops renewing and exits so its process supervisor can replace it. Compose uses `restart: unless-stopped`; the replacement recovers the expired lease. This prevents a thread blocked on a severed PostgreSQL socket from holding a job indefinitely. Embedded development/test workers do not terminate their host API process.

PostgreSQL claims use `SELECT ... FOR UPDATE SKIP LOCKED`; SQLite uses an atomic conditional update. A job records executor, claim time, and lease expiry. Two workers therefore cannot claim the same queued row. Expired `PREPARING` or `IMPORTING` leases are requeued. Expired `CANCELLING` jobs are cancelled. Telemetry writes remain in one transaction, so a terminated worker cannot leave visible partial rows; retries delete rows associated with the import identifier before processing.

Mapped telemetry is sent to the database in 1,000-row SQLAlchemy Core batches while preserving the single transaction. This avoids retaining one ORM object per input row and substantially reduces PostgreSQL import time without exposing partial data.

Cancellation uses a server-controlled marker checked every 250 parsed rows, allowing SQLite cancellation without waiting on its database-wide writer lock. The worker rolls back, records `CANCELLED`, audits, and cleans upload/cancellation files.

## Observability and scaling

`GET /api/v1/admin/system` is administrator-only and reports queue depth, active/cancelling/failed jobs, oldest job, active/stale workers, safe worker status, telemetry count, and forecast count. It never returns telemetry contents or secrets.

Scale workers by increasing the Compose worker replica count. All replicas share PostgreSQL and a persistent `import-data` volume. `ImportStorage` is the boundary between upload/import business logic and object persistence: the API streams writes by stable storage reference, while analyzers and workers use `materialize()` and cancellation methods. `LocalFileImportStorage` supports local paths, Compose volumes, and network-mounted paths through `IMPORT_STORAGE_ROOT`. A future S3 or Azure implementation can download an object into the bounded-lifetime `materialize()` context without changing parsers or workers.

## Startup

Copy `.env.example`, set `POSTGRES_PASSWORD` and `SESSION_SECRET`, then use `docker compose up --build`. Without Docker, use `npm run dev` for SQLite. Apply `alembic upgrade head` before manually starting API/worker processes.

## Tests and load generation

The standard backend suite uses SQLite. Set a PostgreSQL `DATABASE_URL` before test collection to exercise a provisioned PostgreSQL database. Set `RUN_POSTGRES_RUNTIME=1` and explicitly run `tests/postgres/test_runtime_processes.py` only against a disposable PostgreSQL database to exercise real worker processes, crashes, lease recovery, and PostgreSQL restart. The synthetic benchmark generates files at runtime and commits no telemetry fixtures. Its default ceiling is 150,000 rows; set `BENCHMARK_LARGE=1` to include 500,000 and 1,000,000 rows. It reports upload/queue/worker/total time, committed/rejected rows, database growth, peak traced Python memory, and five-sample endpoint median/p95.

## Known limitations

- SQLite cannot persist fine-grained progress while the telemetry transaction holds its single-writer lock.
- The included backend is filesystem-based. Multi-host deployments must point `IMPORT_STORAGE_ROOT` at network/shared storage or add an object-storage implementation of `ImportStorage`.
- Production startup requires both `IMPORT_STORAGE_ROOT` and `IMPORT_STORAGE_PERSISTENT=true`. Set the flag only after attaching a persistent shared Railway volume; it is an explicit deployment acknowledgement, not a substitute for the volume.
- PostgreSQL high-availability/failover behavior beyond single-server restart remains an infrastructure-specific production gate.
