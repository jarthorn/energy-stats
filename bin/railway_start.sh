#!/usr/bin/env bash
set -euo pipefail

# Railway web start command.
# Expects PORT to be set by Railway.

exec uv run gunicorn energystats.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads "${GUNICORN_THREADS:-1}" \
  --timeout "${GUNICORN_TIMEOUT:-60}"

