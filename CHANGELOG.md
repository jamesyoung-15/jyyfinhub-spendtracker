# Changelog

Notable changes per release. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [semantic versioning](https://semver.org/spec/v2.0.0.html).

Migrations run automatically on container start, so an upgrade needs no manual step unless a release
says otherwise under **Upgrade notes**.

## [Unreleased]

### Changed

- Retired the `Subscriptions` category. It overlapped with the subscription checkbox, which already
  records that a charge recurs on any category, so recurring spend no longer gets pulled out of
  `Housing`, `Utility` and `Leisure`.
- Added an `Education` category with `Tuition` and `Self Study`, covering tuition, online courses
  and practice subscriptions.

### Upgrade notes

- The migration recategorises existing rows in both `transactions` and `transaction_templates`, and
  runs automatically on container start. It is intentionally not reversible: `downgrade()` is a
  no-op, because reversing would sweep up rows that never belonged to `Subscriptions`.

## [0.2.0] - 2026-09-18

### Added

- Spend by category on the summary page, showing gross and net per category sorted by net
  descending, with a total row. Categories that use subcategories list them underneath.
- The same breakdown for the whole year, in a collapsed section at the bottom of the page.
- `GET /api/v1/summaries/monthly/{month}/categories` and
  `GET /api/v1/summaries/yearly/{year}/categories`.

## [0.1.0] - 2026-09-13

First release, and the version the real transaction history was first entered against.

### Added

- Transactions with date, merchant, category, subcategory, amount, payment method and notes. The
  entry form defaults the date to today and the card to whichever was used last, and offers a
  merchant datalist built from history.
- Splitting one purchase across categories on a dedicated page. Siblings share an `order_ref` and
  are grouped back together on the detail page with an order total.
- Transaction templates that pre-fill the entry form, shown as chips above it.
- Payment methods with kind, expiry and an active flag, managed through their own pages.
- Reimbursements recorded against a transaction, with gross, received and net shown on the detail
  page and an inline way to mark one received.
- Monthly budget goals, plus a summary page showing gross, reimbursed, net, goal and variance with a
  month by month breakdown and a yearly roll-up.
- A JSON API under `/api/v1` covering all of the above, documented at `/docs`.
- Docker Compose setups for dev, test and prod, with `task prod-up` building and running the full
  stack and `task backup` dumping the database.
- `task restore-check`, which restores the newest backup into a scratch database and migrates it, so
  a migration can be tried against real data before prod sees it.

### Fixed

- Retired payment methods are selectable again. The dropdown filtered to active cards on every form,
  which made it impossible to enter a historical transaction on a cancelled card or to save an edit
  to one already charged to it.
- `task prod-up` and the other prod tasks now load `.env.prod` themselves. The global `.env` was
  exported into the task environment and beat `--env-file`, so the prod stack silently came up on
  dev port, dev debug settings and dev database credentials.
- Write handlers commit their own session. Committing during dependency teardown happened after the
  response had been sent, which let a client read back its own write before it landed.
- Reimbursements are appended to the parent's collection rather than written by foreign key, so a
  loaded transaction no longer keeps a stale list for the rest of the session.
- Enum columns declare their `CHECK` constraint explicitly. Autogenerate could not see one produced
  by `Enum(create_constraint=True)` and dropped it on every run.
- Dates use the configured `TZ` rather than UTC, so an evening entry is no longer dated tomorrow.

[Unreleased]: https://github.com/jamesyoung-15/jyyfinhub-spendtracker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jamesyoung-15/jyyfinhub-spendtracker/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jamesyoung-15/jyyfinhub-spendtracker/releases/tag/v0.1.0
