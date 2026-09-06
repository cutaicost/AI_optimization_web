# AI Optimization Tool Web

Version 0.2.0 establishes the web-first foundation for AI Optimization Tool: a Vite frontend, FastAPI API, SQLAlchemy persistence, server-side sessions, owner-scoped streaming telemetry imports and analytics, and an administrator control plane.

This repository is independent from the desktop application. The first milestone intentionally delivers the platform shell and a secure end-to-end vertical slice; remaining analytics screens identify the next desktop capability to migrate instead of presenting placeholder results as real data.

## Quick start

Requirements: Python 3.11+, Node.js 22+, and PowerShell.

1. Copy `.env.example` to `.env` and provide development values. Admin passwords must be at least 12 characters; omit them if bootstrap accounts are not needed.
2. Create `.venv`, install `apps/api/requirements.txt`, and run `npm install`.
3. Run `alembic upgrade head`.
4. Run `npm run dev` and open `http://127.0.0.1:3000`.

Use `npm run dev:web` and `npm run dev:api` when separate terminals are preferable.

The API is served on port 8000 and Vite proxies `/api` to it. Development defaults to SQLite; production uses PostgreSQL.

## Production containers

Set `POSTGRES_PASSWORD`, a random `SESSION_SECRET` of at least 32 characters, explicit `ALLOWED_ORIGINS`, and optional `ADMIN_SITH_PASSWORD` / `ADMIN_BEYOND_PASSWORD`, then run:

```powershell
docker compose up --build
```

Run database migrations as a release step before directing traffic to a new API version. Terminate TLS at the ingress. Production cookies are always marked Secure.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm test
npm run build
npm audit
```

Architecture, security, migration decisions, and operations are documented in [`docs/`](docs/).

The telemetry schema, import state machine, limits, ownership rules, and next migration stage are documented in [`docs/TELEMETRY.md`](docs/TELEMETRY.md).

The durable worker and advanced analytics behavior are documented in [`docs/ADVANCED_PRODUCT.md`](docs/ADVANCED_PRODUCT.md).

PostgreSQL/SQLite topology, worker heartbeats, job leases, recovery, and scaling are documented in [`docs/ENTERPRISE_RUNTIME.md`](docs/ENTERPRISE_RUNTIME.md).
