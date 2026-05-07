#!/usr/bin/env bash
# Apply alembic migrations against the Railway Postgres (production).
# Reads DATABASE_URL from apps/backend/.env via app.core.config.
#
# Always run scripts/migrate-local.sh first (with a downgrade -1 round-trip)
# before invoking this script.

set -euo pipefail

# Resolve apps/backend regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ ! -f .env ]; then
  echo "ERROR — apps/backend/.env not found. Cannot resolve DATABASE_URL."
  exit 1
fi

echo ">>> Target: RAILWAY (DATABASE_URL from .env)"
echo ">>> alembic upgrade head"
uv run alembic upgrade head

echo ""
echo ">>> alembic current"
CURRENT=$(uv run alembic current 2>&1 | tail -1)
echo "$CURRENT"

if echo "$CURRENT" | grep -q "(head)"; then
  echo ""
  echo "OK — Railway DB is at head."
  exit 0
else
  echo ""
  echo "ERROR — Railway DB is not at head."
  exit 1
fi
