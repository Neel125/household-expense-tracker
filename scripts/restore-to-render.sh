#!/usr/bin/env bash
# Load a local pg_dump into Render Postgres (External connection string).
# Usage:
#   RENDER_DATABASE_URL='postgresql://USER:PASS@HOST/ledger?sslmode=require' \
#     ./scripts/restore-to-render.sh ledger-local.dump.sql
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env.render ]]; then
  # shellcheck disable=SC1091
  set -a
  # quoted values in .env.render
  # shellcheck source=/dev/null
  source .env.render
  set +a
fi

DUMP="${1:-ledger-local.dump.sql}"
URL="${RENDER_DATABASE_URL:-}"

if [[ -z "$URL" ]]; then
  echo "Paste the External Database URL from Render, then press Enter."
  echo "Dashboard → ledger-db → Connect (top right) → External Database URL."
  echo "Do not edit that field in Render — copy it."
  printf "URL: "
  read -r URL
fi
if [[ -z "$URL" ]]; then
  echo "No URL provided." >&2
  exit 1
fi
if [[ ! -f "$DUMP" ]]; then
  echo "Dump file not found: $DUMP" >&2
  echo "Create it first with: ./scripts/dump-local-db.sh" >&2
  exit 1
fi

# SQLAlchemy wants postgresql://; psql accepts both. Render sometimes
# still hands out postgres:// — normalise so ssl query params stick.
if [[ "$URL" == postgres://* ]]; then
  URL="postgresql://${URL#postgres://}"
fi
if [[ "$URL" != *"sslmode="* ]]; then
  if [[ "$URL" == *"?"* ]]; then
    URL="${URL}&sslmode=require"
  else
    URL="${URL}?sslmode=require"
  fi
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required on this machine (postgresql-client)." >&2
  exit 1
fi

echo "Resetting Render public schema, then restoring ${DUMP}…"
psql "$URL" -v ON_ERROR_STOP=1 <<SQL
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;
SQL
psql "$URL" -v ON_ERROR_STOP=1 -f "$DUMP"
echo "Restore finished. Restart the web service in the Render dashboard if it is already running."
