#!/usr/bin/env bash
# Upgrade LBRO on EC2 (docker-compose.prod.yml stack).
#
# Handles divergent git history after force-push: resets to origin/main.
# Does NOT modify .env or postgres volumes.
#
# Usage (from repo root on EC2):
#   bash scripts/ec2_upgrade.sh
#
# Optional: skip backup if you already have one today
#   SKIP_BACKUP=1 bash scripts/ec2_upgrade.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
TARGET_COMMIT="${TARGET_COMMIT:-origin/main}"

echo "=== LBRO EC2 upgrade ==="

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.prod.example to .env first." >&2
  exit 1
fi

if [ "${SKIP_BACKUP:-0}" != "1" ]; then
  echo "--- Step 1: Database backup ---"
  bash "$ROOT/scripts/backup_postgres.sh"
else
  echo "--- Step 1: Skipping backup (SKIP_BACKUP=1) ---"
fi

echo "--- Step 2: Sync git to ${TARGET_COMMIT} ---"
git fetch origin
git reset --hard "$TARGET_COMMIT"
echo "HEAD: $(git log -1 --oneline)"

echo "--- Step 3: Build images ---"
docker compose -f "$COMPOSE_FILE" build

echo "--- Step 4: Run migrations ---"
docker compose -f "$COMPOSE_FILE" run --rm api alembic upgrade head
docker compose -f "$COMPOSE_FILE" run --rm api alembic current

echo "--- Step 5: Restart stack ---"
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

echo "--- Step 6: Wait for health ---"
sleep 15
docker compose -f "$COMPOSE_FILE" ps

echo "--- Step 7: HTTP checks ---"
curl -sf http://localhost:80/health | head -c 200
echo ""
curl -sf http://localhost:80/api/v1/health | head -c 200
echo ""

echo "=== Upgrade complete ==="
echo "Open http://$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo YOUR_EC2_IP) in a browser."
