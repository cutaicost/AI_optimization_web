# Development and operations

## Configuration

Configuration is environment-only. `APP_ENV=production` requires a 32+ character `SESSION_SECRET`, rejects wildcard CORS, and forces Secure cookies. SQLite is the default only when no `DATABASE_URL` is supplied.

Bootstrap administrators are created only when their corresponding environment variable is present. Re-running bootstrap does not change existing accounts or password hashes:

```powershell
.\.venv\Scripts\python.exe scripts\bootstrap-admins.py
```

## Database workflow

Create schema changes in SQLAlchemy models and a matching Alembic revision. Test upgrades and downgrades against a disposable database. PostgreSQL schema compilation is covered in the backend suite; deployment should additionally exercise the revision against the exact supported PostgreSQL image.

## Release checklist

1. Synchronize `VERSION`, API version metadata, and package version.
2. Run backend, frontend, build, audit, and secret-scan checks.
3. Review the migration SQL and back up production data.
4. Apply migrations, deploy API and web images, then verify `/api/v1/health` and authentication.
5. Confirm CSP/CORS/TLS configuration, audit collection, alerts, rollback image, and rollback migration strategy.

Never commit `.env`, databases, generated build output, or virtual environments.
