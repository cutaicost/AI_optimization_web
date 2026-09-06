#!/bin/sh
set -eu

python -c 'import os; [print(f"{name} present: {str(bool(os.environ.get(name))).lower()}") for name in ("DATABASE_URL", "APP_ENV", "SESSION_SECRET", "PROVIDER_CREDENTIAL_MASTER_KEY")]'
python -m alembic upgrade head
python scripts/bootstrap-admins.py
exec uvicorn apps.api.aiopt_web.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
