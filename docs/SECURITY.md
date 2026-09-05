# Security

## Implemented controls

- Argon2id password hashing and generic invalid-credential responses.
- Opaque, hashed, expiring server-side sessions in HttpOnly, SameSite cookies; Secure is mandatory in production.
- Double-submit CSRF validation bound to the server session for state-changing requests.
- Backend-enforced USER/ADMIN RBAC and owner predicates on user data.
- Login throttling keyed by a one-way identity digest.
- Pydantic input constraints, ORM-bound parameters, explicit CORS origins, and restrictive browser headers/CSP.
- Idempotent bootstrap for exactly `Sith` and `Beyond`; passwords come only from environment variables, are stored only as hashes, and require immediate replacement.
- Audit metadata drops keys that appear credential-bearing. Password hashes are never included in response schemas.
- The final active administrator cannot be disabled or demoted.

## Operational requirements

Use a managed secret store, rotate bootstrap credentials after first login, apply Alembic migrations before rollout, terminate TLS, restrict database networking, back up PostgreSQL, and centralize audit/health monitoring. Apply edge rate limiting in addition to application login throttling. Review dependencies and run secret scanning in CI.

This foundation is not a compliance certification. Before a public launch, complete threat modeling, penetration testing, privacy/retention policy work, disaster-recovery exercises, SSO/MFA design, and security logging integration.

## Secret response

If a secret is committed, revoke it first, remove it from all history and artifacts, rotate affected sessions, then audit access. Never treat deletion from the latest commit as sufficient revocation.
