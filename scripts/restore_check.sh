#!/usr/bin/env bash
# Restore the newest backup into a scratch database and migrate it to head.
#
# This is the only check that runs migrations against real data rather than fixtures.
# Run it before applying a new migration to prod. Nothing here touches the prod database:
# the restore goes into the throwaway test container.
set -euo pipefail

DUMP="${1:-$(ls -1t backups/*.dump 2>/dev/null | head -1)}"
SCRATCH="restore_check_test"
TEST_URL="postgresql+psycopg://test:test@127.0.0.1:55432"

if [[ -z "$DUMP" || ! -f "$DUMP" ]]; then
  echo "no dump found: run 'task backup' first, or pass a path" >&2
  exit 1
fi

echo "==> restoring $DUMP into $SCRATCH"
docker compose -f compose.test.yml up -d --wait >/dev/null

psql_admin() { docker compose -f compose.test.yml exec -T db psql -U test -d postgres -q "$@"; }
psql_admin -c "DROP DATABASE IF EXISTS $SCRATCH WITH (FORCE)"
psql_admin -c "CREATE DATABASE $SCRATCH"

# --no-owner: the dump names the prod role, which does not exist in the test container
docker compose -f compose.test.yml exec -T db pg_restore -U test -d "$SCRATCH" --no-owner < "$DUMP"

count_rows() {
  docker compose -f compose.test.yml exec -T db psql -U test -d "$SCRATCH" -tAc \
    "SELECT coalesce(sum(n_live_tup), 0) FROM pg_stat_user_tables WHERE relname <> 'alembic_version'"
}

docker compose -f compose.test.yml exec -T db psql -U test -d "$SCRATCH" -q -c "ANALYZE"
before=$(count_rows)
echo "==> restored at revision $(docker compose -f compose.test.yml exec -T db psql -U test -d "$SCRATCH" -tAc 'SELECT version_num FROM alembic_version')"
echo "==> $before rows before upgrade"

echo "==> alembic upgrade head"
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 POSTGRES_USER=test \
  POSTGRES_PASSWORD=test POSTGRES_DB="$SCRATCH" \
  uv run alembic upgrade head

docker compose -f compose.test.yml exec -T db psql -U test -d "$SCRATCH" -q -c "ANALYZE"
after=$(count_rows)
echo "==> $after rows after upgrade"

psql_admin -c "DROP DATABASE IF EXISTS $SCRATCH WITH (FORCE)"

if [[ "$before" != "$after" ]]; then
  echo "FAILED: row count changed $before -> $after" >&2
  exit 1
fi
echo "OK: migrations applied to real data, $after rows intact"
