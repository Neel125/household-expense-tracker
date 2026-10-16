#!/usr/bin/env bash
# Copy Render Postgres onto the local Docker Compose database (ledger-pg).
# Usage: ./scripts/pull-from-render.sh [outfile.sql]
#
# Reads RENDER_DATABASE_URL from .env.render (gitignored). Stops the app
# container during the restore so it is not querying a half-replaced schema.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env.render ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env.render
  set +a
fi

OUT="${1:-ledger-render.dump.sql}"
URL="${RENDER_DATABASE_URL:-}"

if [[ -z "$URL" ]]; then
  echo "Paste the External Database URL from Render, then press Enter."
  printf "URL: "
  read -r URL
fi
if [[ -z "$URL" ]]; then
  echo "No URL provided. Put it in .env.render as RENDER_DATABASE_URL=…" >&2
  exit 1
fi

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

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump is required (postgresql-client)." >&2
  exit 1
fi

if ! docker compose ps db --status running >/dev/null 2>&1; then
  echo "Starting local Postgres…"
  docker compose up -d db
  docker compose exec db pg_isready -U ledger >/dev/null
fi

echo "Dumping Render → ${OUT}"
pg_dump "$URL" --no-owner --no-acl > "$OUT"
echo "Dump size: $(wc -c < "$OUT") bytes."

echo "Stopping the local app so it does not query a half-replaced schema…"
docker compose stop app >/dev/null 2>&1 || true

echo "Replacing local public schema…"
docker compose exec -T db psql -U ledger -d ledger -v ON_ERROR_STOP=1 <<SQL
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;
SQL
docker compose exec -T db psql -U ledger -d ledger -v ON_ERROR_STOP=1 < "$OUT"

echo "Starting the local app…"
docker compose up -d app

echo "Done. Local http://127.0.0.1:8000 now has the Render copy. Hard-refresh the UI."
