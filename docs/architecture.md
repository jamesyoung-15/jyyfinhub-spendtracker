# Project Architecture

- [Project Architecture](#project-architecture)
  - [Stack](#stack)
  - [Layout](#layout)
  - [Package rules](#package-rules)
  - [Database and sessions](#database-and-sessions)
  - [Migrations](#migrations)
  - [Web layer](#web-layer)
  - [Testing](#testing)
  - [Tasks](#tasks)

## Stack

FastAPI, Postgres 18, SQLAlchemy 2 (async, `psycopg` 3), Alembic (sync), Jinja2 + plain CSS,
pytest + pytest-asyncio, uv / ruff / pyright / pre-commit, go-task.

I picked `psycopg` over `asyncpg` because one driver covers both sync and async, which lets Alembic
stay sync while the app runs async.

The application is simple enough that it needs no frontend framework and only a few lines of JS.

## Layout

```txt
jyyfinhub-spendtracker/
├── src/jyyfinhub_spendtracker/
│   ├── main.py                  # create_app(), exception handlers, static mount
│   ├── api.py                   # api_router, mounts feature routers under /api/v1
│   ├── deps.py                  # shared Depends
│   ├── categories.py            # SPEND_CATEGORIES, is_valid_pair(), InvalidCategoryPair
│   ├── core/                    # config.py, logging.py, exceptions.py
│   ├── db/                      # base.py, session.py, registry.py
│   ├── transactions/            # + Reimbursement, splits
│   ├── transaction_templates/
│   ├── payment_methods/         # + seed.py
│   ├── goals/
│   ├── summaries/               # no models, reads the others
│   └── web/                     # one module per page group, templates/, static/
├── tests/                       # mirrors the feature packages
├── alembic/versions/
├── scripts/restore_check.sh
├── docs/
├── compose.yml, compose.test.yml, compose.prod.yml
├── Dockerfile, entrypoint.sh, Taskfile.yml
└── CLAUDE.md -> AGENTS.md
```

Everything is organised by feature, with each feature package sitting at the package root. A feature
package normally holds `models.py`, `schemas.py`, `service.py`, `router.py` and `exceptions.py`,
though some vary: `summaries/` has no models and `payment_methods/` adds `seed.py`.

## Package rules

- `db/` holds infrastructure only, so models live in whichever feature package owns them.
- Avoid `constants.py`, `utils.py` and `helpers.py`. Modules should be named for what they are about.
- Enums live beside the model that passes them to `sa.Enum`.
- Package boundaries follow aggregates rather than tables, which is why `Reimbursement` sits inside
  `transactions/`.
- Cross-package references use strings, as in `ForeignKey("transactions.id")` and
  `relationship("Transaction")`.
- A domain rule that two packages both need moves up to the package root. `categories.py` lives
  there so `transactions` and `transaction_templates` never have to import each other.
- Services raise domain exceptions from `core/exceptions.py` and never `HTTPException`. The handler
  in `main.py` translates them into JSON under `/api` and an HTML error page everywhere else.
- Dependency arrows point one way. `summaries/` reads from the other features and nothing reads
  from it.

## Database and sessions

Tables and relationships are in [Schema](./schema.md).

- Amounts are integer cents throughout, so no float ever touches money. `web/forms.py` converts
  dollars with `Decimal` and `ROUND_HALF_UP`.
- Each request gets one transaction, committed by the handler. Services only `flush()`, which lets a
  handler call several of them and still end up with one atomic unit.
- `get_session` deliberately leaves the commit to the handler. Dependency teardown runs after the
  response has been sent, so committing there would let a client read back its own write before it
  landed. Write handlers finish with `await session.commit()`.
- Nothing lazy loads under async. Relationships are declared `lazy="raise"` and loaded eagerly with
  `selectinload()`, and sessions use `expire_on_commit=False`.
- `Base.metadata` carries a `naming_convention` so every constraint can be dropped by name.
- Enum columns use `sa.Enum(..., native_enum=False, create_constraint=False)` alongside an explicit
  `CheckConstraint` in `__table_args__`. Alembic cannot see a constraint that the `Enum` type
  generated for it, so `create_constraint=True` produces a diff that comes back on every
  autogenerate run.

### Gotchas worth remembering

These all cost real debugging time.

- A failed flush poisons the whole session, which leaves the caller unable to re-render a form. Wrap
  any mutation that might trip a constraint in `async with session.begin_nested()`, and make sure
  the `add`, `setattr` or `delete` happens inside that block rather than before it.
- Append to a relationship rather than setting the foreign key when the parent might already be
  loaded. Setting `transaction_id` directly leaves the parent's collection stale for the rest of the
  session, and the identity map then hands that stale object to the next query.
- A form normaliser that always writes a key defeats `exclude_unset`. A partial form has to omit the
  fields it did not carry, otherwise an absent field arrives as an explicit null and wipes whatever
  was stored.

## Migrations

- `db/registry.py` imports and re-exports every model class in `__all__`, and `alembic/env.py`
  imports `Base` from there so that `Base.metadata` is always complete. Forgetting a model would
  produce a migration that drops its table, which `test_all_models_registered` guards against.
- `alembic/env.py` uses an already-set `sqlalchemy.url` when it finds one and otherwise falls back
  to settings. That is what lets the migration tests point Alembic at a throwaway database.
- Never edit or delete a migration that has been applied. A database stamped with a revision that no
  longer exists on disk cannot upgrade, and recovering means either `alembic stamp` or wiping the
  data.

## Web layer

- Pages are server-rendered Jinja2. Forms POST and then redirect with a 303, and the browser never
  sees JSON.
- Each page group gets its own module in `web/`, all pulled together by `web/routes.py`. The
  templates mirror the same split.
- A validation failure re-renders the form with a 422 and keeps whatever was typed, rather than
  redirecting or returning JSON.
- `web/splits.py` has to be included before `web/transactions.py`, otherwise
  `/transactions/{transaction_id}` swallows `/transactions/split`. A test reads the OpenAPI paths to
  keep that honest.
- The theme is dark only, with CSS custom properties at the top of `static/style.css`.
- Icons are inlined with `{% include %}` so they inherit `currentColor`.

## Testing

- `tests/conftest.py` builds the schema with `create_all` and wraps each test in a savepoint that is
  rolled back afterwards, so tests share one database without ever seeing each other's rows.
- The `client` fixture overrides `get_session` with that same session, which means route tests share
  a single connection and cannot catch read-after-write bugs. Only a real run against Postgres will
  find those.
- `tests/test_migrations.py` works differently and runs Alembic for real against its own throwaway
  database, one per test. It covers upgrade, downgrade, replay, drift against the models, and
  whether data survives the latest revision.
- `pytest_configure` refuses to run unless the database name ends in `_test`, since the engine
  fixture calls `drop_all`.

## Tasks

`task --list` shows everything. The ones worth knowing:

- `task dev` brings up the dev db, migrates, then serves with reload
- `task test` starts the tmpfs test db and runs the suite, and `task test -- -k foo` filters it
- `task check` runs ruff and pyright
- `task prod-up` builds and runs the full stack against `.env.prod`
- `task backup` dumps prod to `backups/`
- `task restore-check` restores the newest backup into a scratch db and migrates it

Every `prod-*` task sets its own `dotenv: [".env.prod"]`. The global `dotenv: [".env"]` gets
exported into the task environment, and a real environment variable wins over `--env-file` during
Compose interpolation, so without that override `task prod-up` quietly builds prod from dev values.
