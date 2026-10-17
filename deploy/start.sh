#!/bin/sh
# Production entrypoint: apply migrations, then serve the API and the built frontend.
set -e
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi
# One worker by default: rate limits and the optional sync scheduler live in the process, so more
# workers multiply the limits and would run the scheduler once per worker.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" --no-access-log
