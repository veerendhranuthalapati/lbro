#!/usr/bin/env bash
# Backup LBRO PostgreSQL from docker-compose.prod.yml stack.
# Uses credentials from INSIDE the postgres container (reads .env via Compose).
#
# Usage (from repo root on EC2):
#   bash scripts/backup_postgres.sh
#   bash scripts/backup_postgres.sh /path/to/backup.sql
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
OUT="${1:-lbro-backup-$(date +%Y%m%d-%H%M%S).sql}"

if ! docker compose -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -qE 'running|Up'; then
  echo "ERROR: postgres service is not running. Start the stack first." >&2
  exit 1
fi

echo "Writing backup to: $OUT"
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$OUT"

SIZE=$(wc -c < "$OUT" | tr -d ' ')
if [ "$SIZE" -lt 100 ]; then
  echo "ERROR: backup file is too small (${SIZE} bytes) — dump may have failed." >&2
  head -5 "$OUT" >&2 || true
  exit 1
fi

echo "OK: backup complete ($(numfmt --to=iec "$SIZE" 2>/dev/null || echo "${SIZE} bytes"))"
head -1 "$OUT"
