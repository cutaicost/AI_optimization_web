#!/bin/sh
set -eu

python -m alembic upgrade head
python scripts/bootstrap-admins.py
exec uvicorn apps.api.aiopt_web.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
