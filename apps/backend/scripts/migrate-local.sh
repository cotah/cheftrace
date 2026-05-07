#!/usr/bin/env bash
# Apply alembic migrations against the LOCAL Postgres on port 5433.
# Use this for round-trip testing (upgrade + downgrade) before deploying.
#
# Requires: docker container `cheftrace-test` running, e.g.
#   docker run -d --name cheftrace-test -p 5433:5432 \
#     -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
#     postgres:16

set -euo pipefail

# Resolve apps/backend regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

LOCAL_DB="postgresql+asyncpg://test:test@localhost:5433/test"

echo ">>> Target: LOCAL Postgres ($LOCAL_DB)"
echo ">>> alembic upgrade head"
DATABASE_URL="$LOCAL_DB" uv run alembic upgrade head

echo ""
echo ">>> alembic current"
CURRENT=$(DATABASE_URL="$LOCAL_DB" uv run alembic current 2>&1 | tail -1)
echo "$CURRENT"

if echo "$CURRENT" | grep -q "(head)"; then
  echo ""
  echo "OK — local DB is at head."
  exit 0
else
  echo ""
  echo "ERROR — local DB is not at head."
  exit 1
fi
