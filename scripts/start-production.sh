#!/bin/sh
set -eu

# Railway mounts volumes as root. Initialize only the dedicated import path,
# then permanently drop privileges before migrations or application startup.
if [ "$(id -u)" = "0" ]; then
  mkdir -p /var/lib/aiopt/imports
  chown app:app /var/lib/aiopt/imports
  exec gosu app "$0" "$@"
fi

python -c 'import os; [print(f"{name} present: {str(bool(os.environ.get(name))).lower()}") for name in ("DATABASE_URL", "APP_ENV", "SESSION_SECRET", "PROVIDER_CREDENTIAL_MASTER_KEY")]'
python -m alembic upgrade head
python scripts/bootstrap-admins.py
exec uvicorn apps.api.aiopt_web.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
