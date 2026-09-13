# Application Deployment

Runs on a homelab VM and is reachable only over WireGuard. `git clone` followed by `task prod-up` is
the whole setup.

## Compose files

There are three, and each one sets an explicit `name:`. Compose otherwise derives the project name
from the directory, which makes dev and test collide so that only one `db` container can exist.

- `compose.yml` (`spendtracker-dev`) runs the db on its own while the app runs on the host with
  reload.
- `compose.test.yml` (`spendtracker-test`) runs the db on port 55432 with a `tmpfs` data directory
  and `fsync=off`, since everything in it is meant to be thrown away.
- `compose.prod.yml` (`spendtracker`) runs both db and api. The db publishes no port at all and the
  api reaches it by service name.

Every container sets `TZ`, because they default to UTC and an evening entry would otherwise be dated
tomorrow.

Postgres 18 keeps `PGDATA` at `/var/lib/postgresql/18/docker` underneath the `/var/lib/postgresql`
volume, which is worth re-checking on any major version bump.

## Image

Two stages share the same `python:3.13-slim-bookworm` base so that the venv's interpreter path
exists in both. The result is around 240MB and runs as a non-root user.

- Dependencies install before the source is copied, so editing code does not rebuild them.
- `--no-editable` copies the package into the venv, which leaves the runtime stage with no need for
  `src/`.
- `alembic.ini` and `alembic/` are copied explicitly, since they are not part of the package.

`entrypoint.sh` runs `alembic upgrade head` and then hands over with `exec uvicorn`, so uvicorn
becomes PID 1 and receives SIGTERM. There is no gunicorn in front, as one worker is plenty for a
single user.

## Config

Dev reads `.env` and prod reads `.env.prod`. Both are gitignored, and `.env.example` is committed.

- `POSTGRES_HOST` and `POSTGRES_PORT` are hardcoded in `compose.prod.yml`, so the values sitting in
  `.env.prod` only matter for host-side tooling.
- Every `prod-*` task needs its own `dotenv: [".env.prod"]`. The global `dotenv: [".env"]` gets
  exported into the task environment, and a real environment variable wins over `--env-file` during
  Compose interpolation, so without that override `task prod-up` quietly builds prod from dev
  values.

## Access

There is no application auth, and two layers sit in front instead.

- WireGuard, so nothing is published to the public internet.
- Nginx on the host, outside the compose stack, proxying to `127.0.0.1:${APP_PORT}`. Basic auth
  belongs here if a second layer is ever wanted.

`APP_HOST` stays on `127.0.0.1` so the api can only be reached by the reverse proxy on the same box.

## Backups

- `task backup` writes a timestamped `pg_dump --format=custom` into `backups/`.
- `task restore-check` loads the newest dump into a scratch db and migrates it, comparing row counts
  either side. Run it after writing a migration and before applying that migration to prod.
- Dumps land on the same box as the database, so copy them off it. `docker compose down -v` deletes
  the volume.
