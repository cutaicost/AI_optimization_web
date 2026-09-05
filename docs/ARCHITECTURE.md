# Architecture

## Boundaries

- `apps/web`: framework-light Vite client and responsive application shell. It owns presentation and routing, never authorization.
- `apps/api`: FastAPI HTTP boundary, validation, authentication, RBAC, ownership filters, and application services.
- SQLAlchemy models: portable persistence mapping. PostgreSQL is the production target; SQLite supports local development and isolated tests.
- `migrations`: Alembic is the production schema authority. Startup table creation is a development convenience and is not the deployment migration strategy.

The browser holds an opaque session identifier in an HttpOnly cookie and a readable CSRF token in a second cookie. The database stores only hashes of both. Every data query is scoped using the authenticated user identifier. Administrative access is checked in API dependencies, not inferred from navigation visibility.

## Data model

`users` own sessions, telemetry, import jobs, budgets, forecast runs, integrations, provider configurations, price overrides, and model evaluations. Audit events record security and administrative actions without credentials. Reserved domain tables let later milestones migrate desktop capabilities without redesigning identity or ownership.

## Routes

Public routes are `/`, `/login`, and `/register`. Authenticated routes live under `/app`; `/app/admin/*` additionally requires the ADMIN role. Bootstrap administrators must change their password before product or administrator operations.

## Deployment

The compose topology is browser -> Nginx -> FastAPI -> PostgreSQL. Nginx serves immutable built assets and proxies `/api`. The API is stateless apart from the database-backed session store, permitting horizontal replicas behind a TLS ingress.
