#!/bin/sh
set -e

# Optional one-off load of the sample September 2026 data. seed.py is
# idempotent — it skips if the database already has transactions.
case "${SEED_DATA:-false}" in
  1|true|TRUE|yes) python seed.py ;;
esac

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
