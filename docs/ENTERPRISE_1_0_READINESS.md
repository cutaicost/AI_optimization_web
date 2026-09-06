# TokenScope 1.0 Enterprise Readiness

Assessment date: 2026-09-06. Candidate version remains `0.2.0`; `1.0.0-rc.1` is not justified while mandatory gates are blocked or partial.

## Deployment modes

Local Desktop Mode is the Tauri desktop application, a loopback-only FastAPI sidecar, SQLite, local import storage, DPAPI-protected secrets, and per-launch local authentication. This repository contains no Tauri/Rust workspace, so packaging, signing, sidecar lifecycle, and desktop authentication cannot be validated here.

Enterprise Server Mode is the FastAPI API, independently scalable workers, PostgreSQL, a shared `IMPORT_STORAGE_ROOT`, generic OIDC, and authoritative RBAC. The storage root must be a durable volume mounted at the same path in API and worker containers. Object-store implementations and PostgreSQL HA are explicitly post-1.0 work.

## Readiness matrix

| Area | Status | Evidence / remaining work |
|---|---|---|
| PostgreSQL runtime | PASS | PostgreSQL 17.11; clean Alembic migration reaches `0006`; prior restart validation passed. |
| Multi-worker ownership | PASS | PostgreSQL `FOR UPDATE SKIP LOCKED`, conditional claims, leases, and exactly-once ownership validated. |
| Crash recovery | PASS | PREPARING, IMPORTING, CANCELLING, worker termination, and PostgreSQL restart scenarios validated in the enterprise-runtime milestone. |
| Durable storage | PASS | `ImportStorage` and `LocalFileImportStorage`; durable references and shared/network-mounted `IMPORT_STORAGE_ROOT`. |
| OIDC | PARTIAL | Vendor-neutral discovery, authorization-code flow, PKCE, state, nonce, JWKS signature, issuer, audience, expiration, and claim mapping implemented. Cryptographic negative tests pass; no local Keycloak/Docker or production tenant was available for an end-to-end provider redirect. |
| RBAC | PASS | Viewer, Analyst, Administrator enforced by backend dependencies and tested with authenticated sessions. |
| Secret storage | PASS | Server secrets are environment/deployment injected; desktop abstraction uses Windows DPAPI. Save, retrieve, rotate, delete, mask, and diagnostic redaction tests pass. |
| Backup / restore | PASS | PostgreSQL custom-format archive, AES-256-GCM encryption, checksum/schema validation, populated restore, transactional rollback, and recovery backup tested. Operator audit integration remains PARTIAL under Audit. |
| Retention | PARTIAL | 30/90/180/365/unlimited preview and transactional execution implemented; configuration and audit records preserved. Large PostgreSQL dataset test is outstanding. |
| Migration | PASS | Realistic `0005` fixture upgrades to `0006` preserving enterprise entities; PostgreSQL transactional DDL failure leaves source data intact. |
| Audit | PARTIAL | Actor, role, UTC timestamp, action, resource, outcome, safe metadata, and protected JSON/CSV export exist. Backup/restore and systematic authorization-failure audit coverage remain incomplete. |
| Diagnostics | PASS | Safe version, schema, DB health/type, queue, worker, import, storage, OIDC/RBAC, runtime, row counts, and uptime fields with JSON export; secrets excluded. |
| Search | DEFERRED | Reduced compatibility search filtering/ranking is not a mandatory runtime gate and has not been completed. |
| Reports | PARTIAL | Executive JSON/CSV exists; richer executive detail and explicit export auditing remain. |
| Importer | PARTIAL | Streaming, bounded chunks, 500 MB limit, detection, cancellation, rejected rows, transactional persistence, and multi-worker safety pass. Explicit KEEP/SKIP/REJECT duplicate policy remains. |
| SSE | DEFERRED | Snapshot behavior remains; production continuous SSE was not forced into this release candidate. |
| Desktop mode | BLOCKED | No Tauri/Rust project exists in this repository; desktop validation would require the separately scoped desktop repository. |
| Server mode | PARTIAL | Native PostgreSQL runtime passes. Docker runtime and provider-backed OIDC end-to-end validation are unavailable on this host. |
| Deployment | PARTIAL | Compose pins major images, has health checks, keeps PostgreSQL unexposed, shares import storage, and retains `restart: unless-stopped` for workers. Non-root/read-only container validation remains. |
| Security | PARTIAL | Server sessions, CSRF, secure-cookie production rules, Argon2, OIDC validation, secret redaction, and zero npm vulnerabilities pass. Container and live-IdP gates remain. |
| Accessibility | PARTIAL | Playwright viewport checks pass; a formal accessibility audit is outstanding. |
| Performance | PASS | PostgreSQL 150k/500k/1M ingestion and 1M analytics regression suite passed in the enterprise-runtime milestone. |
| Signing | BLOCKED | Trusted Authenticode certificate and signed desktop artifacts are external distribution requirements and are not present. |

## Secrets inventory

- Provider and enterprise connector credentials: environment-variable references only in server mode; values are never returned by integration APIs.
- OIDC client secret, database credentials, session secret, bootstrap passwords, and backup encryption key: deployment-injected environment secrets.
- Runtime session/CSRF/OIDC state tokens: hashed in the database where persistence is required and transported in appropriately scoped cookies.
- Windows desktop credentials: DPAPI abstraction, encrypted for the current Windows user.
- Frontend storage: authentication and secrets are not stored in `localStorage` or `sessionStorage`.
- Diagnostics, audit metadata, and backup manifests exclude secret values. PostgreSQL backups are encrypted; the encryption key is never embedded in the archive or manifest.

## Upgrade procedure

1. Stop API and worker writers and take an encrypted PostgreSQL backup with `scripts/postgres-backup.py`.
2. Verify its checksum and schema metadata before continuing.
3. Preserve the source database and run `alembic upgrade head` against a staged copy first.
4. Validate `alembic current` reports `0006`, entity counts match, and smoke-test authentication, imports, reports, and administration.
5. Upgrade production, then start API and workers. If migration fails, PostgreSQL transactional DDL rolls back; retain the untouched source/recovery backup rather than attempting destructive repair.

## Application blockers

- Complete explicit importer duplicate policies: KEEP, SKIP, REJECT.
- Complete audit coverage for authorization failures, backup/restore, and report exports.
- Validate retention on a large PostgreSQL dataset.
- Complete richer executive reporting and reduced compatibility search where required for 1.0.
- Validate/harden non-root and read-only container operation.

## External infrastructure / distribution blockers

- A real OIDC tenant (or local Keycloak) for provider end-to-end redirect validation.
- Docker/Compose runtime availability on the validation host.
- The separately scoped Tauri/Rust desktop workspace and a trusted Authenticode signing certificate.
- Production PostgreSQL HA and cloud object-storage credentials are post-1.0 capabilities, not claims of this candidate.

## Latest gate results

- SQLite backend: 33 passed.
- OIDC/RBAC/enterprise/security tests are included in those 33 and pass.
- Frontend: 6 passed; production Vite build passed; `npm audit` reports 0 vulnerabilities.
- Playwright: 5 passed at 1920x1080, 1600x900, 1366x768, and 1024x768.
- PostgreSQL encrypted backup/restore: 1 passed.
- Pre-1.0 PostgreSQL upgrade/failure recovery: 1 passed.
- Rust/Tauri and Docker/Compose: BLOCKED by absent workspace/runtime.

No release-candidate commit or version change is permitted until all mandatory application gates pass.
