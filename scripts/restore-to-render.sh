#!/usr/bin/env bash
# Load a local pg_dump into Render Postgres (External connection string).
# Usage:
#   RENDER_DATABASE_URL='postgresql://USER:PASS@HOST/ledger?sslmode=require' \
#     ./scripts/restore-to-render.sh ledger-local.dump.sql
set -euo pipefail
cd "$(dirname "$0")/.."

DUMP="${1:-ledger-local.dump.sql}"
URL="${RENDER_DATABASE_URL:-}"

if [[ -z "$URL" ]]; then
  echo "Set RENDER_DATABASE_URL to the database's External connection string" >&2
  echo "(Render Dashboard → ledger-db → Info → External Connection String)." >&2
  echo "Append ?sslmode=require if it is not already there." >&2
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

echo "Restoring ${DUMP} → Render Postgres…"
psql "$URL" -v ON_ERROR_STOP=1 -f "$DUMP"
echo "Restore finished. Restart the web service in the Render dashboard if it is already running."
