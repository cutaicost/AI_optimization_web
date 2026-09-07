FROM node:22.19.0-alpine3.22 AS frontend-build
WORKDIR /build
COPY package.json package-lock.json vite.config.js ./
COPY apps/web ./apps/web
RUN npm ci && npm run build

FROM python:3.11.13-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    EMBEDDED_IMPORT_WORKER=true \
    IMPORT_STORAGE_ROOT=/var/lib/aiopt/imports
WORKDIR /app
COPY apps/api/requirements.production.txt ./apps/api/requirements.production.txt
RUN pip install --no-cache-dir -r apps/api/requirements.production.txt \
    && addgroup --system app \
    && adduser --system --ingroup app app
COPY apps/api ./apps/api
COPY migrations ./migrations
COPY scripts/bootstrap-admins.py scripts/start-production.sh ./scripts/
COPY alembic.ini VERSION ./
COPY --from=frontend-build /build/dist ./dist
RUN chmod +x /app/scripts/start-production.sh \
    && mkdir -p /var/lib/aiopt/imports \
    && chown -R app:app /app /var/lib/aiopt
USER app
EXPOSE 8000
CMD ["/app/scripts/start-production.sh"]
