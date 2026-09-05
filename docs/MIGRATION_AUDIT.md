# Desktop-to-web migration audit

The existing desktop repository remains untouched and is the behavioral reference, not the deployment base.

## Reuse or adapt

- Provider pricing, token/cost calculations, aggregations, forecasting, recommendations, imports, and evaluation rules can be migrated as framework-independent Python services after parity tests capture desktop behavior.
- Existing Pydantic validation and SQLAlchemy domain concepts can be adapted, adding an authenticated owner identifier to every user-visible record.
- API/provider integrations can be reused only after credentials move to encrypted server-side storage and requests are scoped to the owner.

## Replace

- Desktop window, tray, installer, sidecar, local-process, and per-launch lifecycle code has no web runtime role.
- Local filesystem assumptions, device-global settings, and singleton databases must become explicit database records with ownership and transaction boundaries.
- Desktop navigation and state storage must become URL routes plus API-backed server state.

## Migration order

1. Completed foundation: identity, sessions, RBAC, profile, admin control plane, ownership model, and overview telemetry slice.
2. Ingestion/import with job progress, cancellation, validation reports, and idempotency.
3. Analytics, provider/model/application drill-down, trends, budgets, and exports.
4. Forecasting, recommendations, evaluations, and guarded reset flows.
5. Integrations and cloud configuration with encrypted credentials and connection tests.
6. Enterprise additions: SSO/MFA, organization tenancy, policy controls, background workers, observability, retention, and compliance evidence.

Each migration must include parity fixtures, cross-user isolation tests, authorization tests, empty/loading/error states, and an audit-event review before its UI is considered complete.
