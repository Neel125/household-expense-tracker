#!/usr/bin/env bash
# Dump the Docker Compose Postgres volume (ledger-pg) to a SQL file.
# Usage: ./scripts/dump-local-db.sh [outfile.sql]
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-ledger-local.dump.sql}"

if ! docker compose ps db --status running >/dev/null 2>&1; then
  echo "Postgres is not running. Start it with: docker compose up -d db" >&2
  exit 1
fi

echo "Dumping local ledger database → ${OUT}"
docker compose exec -T db pg_dump -U ledger -d ledger \
  --no-owner --no-acl --clean --if-exists > "$OUT"

echo "Done. $(wc -c < "$OUT") bytes."
echo "Restore on Render with: RENDER_DATABASE_URL='…' ./scripts/restore-to-render.sh ${OUT}"
