# JYYFinHub Spend Tracker

My own spend tracker application that allows me to manually log individual transactions that rolls
up into monthly and yearly spend tracked against a budget goal.

<!-- screenshots go here -->

## About

Hobby and learning project and to replace the spreadsheet I
used to track spending in.

I prefer logging transactions by hand rather than reading off a statement, because a statement line
does not always describe what was actually bought. A single Amazon order arrives as one charge even
though it might be half groceries and half tech hobby items, and a year-long subscription lands as
one payment that would make that month look expensive and the next eleven look cheap. Logging by
hand lets me record both the way I actually think about them.

The spreadsheet handled that fine, but repeat transactions were slow to type. Therefore, the project prioritizes entry speed, where it adds QOL features like templates and uses proper HTML form inputs for quicker entry.

More background is in [docs/README.md](docs/README.md).

## Setup

### Requirements

- Python 3.13
- uv
- Docker + Docker Compose

Task runner commands come from [go-task](https://taskfile.dev), installed as a dev dependency, so
`uv run task ...` works without installing anything globally.

### Development Setup

```sh
git clone <repo> && cd jyyfinhub-spendtracker
uv sync
cp .env.example .env     # then set POSTGRES_PASSWORD
task dev                 # starts the db, migrates, serves on 127.0.0.1:8000
```

`task dev` leaves the database container running after you stop the server, so later sessions only
need `task serve`.

### Testing

```sh
task test                # spins up a throwaway tmpfs db and runs the suite
task test -- -k web      # pass pytest args through
task check               # ruff and pyright
```

### Deployment

```sh
cp .env.example .env.prod   # set POSTGRES_PASSWORD, APP_PORT, APP_DEBUG=false
task prod-up                # builds the image and runs the full stack
```

Migrations run automatically on container start. See [docs/deployment.md](docs/deployment.md) for
the compose layout, reverse proxy and backups.

## Docs

- [Overview](docs/README.md) - what it does and the domain decisions behind it
- [Architecture](docs/architecture.md) - stack, repo layout, package rules, conventions, testing
- [Schema](docs/schema.md) - ER diagram and the constraints behind it
- [Deployment](docs/deployment.md) - containers, compose, config, access, backups
