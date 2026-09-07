#!/bin/sh
set -e

# migrations run before the server accepts traffic
alembic upgrade head

# always bind 0.0.0.0 inside the container; who can reach it is decided by the compose
# port mapping, not by the app
exec uvicorn jyyfinhub_spendtracker.main:app --host 0.0.0.0 --port 8000
