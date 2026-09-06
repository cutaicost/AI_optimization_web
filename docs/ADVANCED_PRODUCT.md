# Worker and advanced product layer

## Durable import execution

`POST /import/{id}/commit` validates the mapping, records `QUEUED`, and returns HTTP 202. A separate `python -m apps.api.aiopt_web.worker` process atomically claims one queued row, transitions through `PREPARING` and `IMPORTING`, and commits telemetry transactionally. Conditional database updates prevent duplicate claims. Interrupted claims older than 15 minutes are explicitly requeued; retries delete any rows carrying the same import identifier before processing.

Cancellation changes running work to `CANCELLING`. The worker checks at bounded parsing/validation checkpoints, rolls back uncommitted telemetry, marks `CANCELLED`, audits, and removes the temporary file. Development and containers start a dedicated worker. Tests may enable the same database worker loop inside the API process; this is not the production deployment model.

SQLite cannot expose transactional row progress while holding its single-writer lock, so intermediate processed-row persistence remains limited there. PostgreSQL is the intended production database for concurrent workers; runtime PostgreSQL validation is still pending.

## Advanced analytics

- Forecasts use a trailing observed daily mean and empirical interval. Seven observed days are required. Runs persist owner, parameters, result, and source window.
- Optimization reports observed cost concentration. It deliberately leaves savings unset without equivalent-model pricing and quality evidence.
- Anomalies use a deterministic trailing 7–28 day ratio baseline for requests, tokens, spend, and latency.
- Budgets provide owner-scoped CRUD, monthly spend progress, warning threshold, and over-budget state.
- Scenario Lab persists validated numeric assumptions and calculated monthly/annual cost; output quality is explicitly not evaluated.
- Reports export owner-scoped JSON or formula-injection-hardened CSV.
- Integrations persist non-secret configuration and an environment-variable reference. Secret values are resolved only through the `SecretStore` abstraction and never returned to browsers.

Every resource lookup includes `user_id`; guessed identifiers belonging to another user return 404. State changes require CSRF validation and emit safe audit events.
