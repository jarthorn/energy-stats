#!/usr/bin/env bash
set -euo pipefail

# Railway deploy hook: run safe, idempotent steps on each deploy.
# Intentionally does NOT backfill data.

uv run python manage.py check --deploy
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput

