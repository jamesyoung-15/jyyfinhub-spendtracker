# JYYFinHub SpendTracker Documentation

## Project Overview

FastAPI web application where I manually log individual transactions, roll them up to monthly and
yearly spend, and compare that against a budget goal.

Single user and self-hosted. Built as hobby and learning project as well as to replace my old method of manually tracking transactions via spreadsheet. Initially hand-wrote parts of the code, later deferred to LLM to speed development up and avoid repeating boiler-plate CRUD stuff.

## Project Motivation

I prefer logging transactions by hand rather than reading off a statement, because a statement line
does not always describe what was actually bought. Some examples include:

- A single Amazon order arrives as one line on my credit card statement, even though the order
  itself might be half groceries and half tech hobby items. Splitting one purchase across
  categories is what `order_ref` exists for.
- A year-long subscription is charged once up front, which would make that month look expensive and
  the next eleven look cheap. I enter it as a monthly share across the months it actually covers
  and flag those rows with `is_subscription`, so each month carries its real cost.

Before this I entered transactions into a spreadsheet, first Proton Sheets then LibreOffice Calc.
That worked, but repeat transactions were slow to type. Templates and proper HTML form inputs fix
that, which is why entry speed is treated as a hard requirement rather than a nice-to-have.

## What it does

- Log a transaction with its date, merchant, category, amount, payment method and notes
- Reuse saved templates for recurring spend, so common entries take about two clicks
- Split one purchase across categories by grouping the rows under a shared `order_ref`
- Record reimbursements against a transaction, so net spend comes out below gross
- Set a monthly budget goal and see the variance against it
- Roll months up into a yearly view

## Domain decisions

- This is a budgeting tool rather than a mirror of my statements, so whether it reconciles against
  the bank does not matter.
- Amounts are integer cents, keeping floats well away from money.
- Every row counts toward its own month. There are no parent rows and nothing is excluded from
  totals.
- A split is several ordinary transactions sharing an `order_ref`, so no stored total can ever
  disagree with the rows that make it up.
- Reimbursements credit the month the spending happened in, even when the money arrives later.
- Net floors at zero per transaction, which stops an over-reimbursed row from making other spending
  look cheaper than it was.
- Monthly goals are the source of truth and the yearly goal is simply their sum.
- Entry speed is a hard requirement, and everything above serves it.

## Main Docs

- [Architecture](./architecture.md) - stack, repo layout, package rules, conventions, testing
- [Schema](./schema.md) - ER diagram and the constraints behind it
- [Deployment](./deployment.md) - containers, compose, migrations, configuration
