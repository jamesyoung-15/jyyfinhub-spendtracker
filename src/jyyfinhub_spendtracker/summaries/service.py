"""Budget math: gross spend, reimbursements, net, and variance against the goal.

Aggregated in SQL rather than by loading rows. `Transaction.net_cents` applies the same clamp for
one transaction, but summing a year of objects in Python would load every row.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.goals.models import MonthlyBudgetGoal
from jyyfinhub_spendtracker.goals.service import list_goals_for_year, month_start_of
from jyyfinhub_spendtracker.summaries.schemas import MonthlySummary, YearlySummary
from jyyfinhub_spendtracker.transactions.models import (
    Reimbursement,
    ReimbursementStatus,
    Transaction,
)
from jyyfinhub_spendtracker.transactions.service import month_bounds, year_bounds


@dataclass(frozen=True)
class Totals:
    """Raw aggregates before a goal is attached."""

    transaction_count: int
    gross_cents: int
    received_cents: int
    net_cents: int


def _base_query() -> Select[tuple[int, int, int, int]]:
    """Transactions joined to the money actually received against each one.

    Only RECEIVED counts. The clamp is per transaction, so being over-reimbursed on one dinner
    cannot make other spending that month look cheaper.
    """
    received_per_transaction = (
        select(
            Reimbursement.transaction_id.label("transaction_id"),
            func.sum(Reimbursement.amount_cents).label("received_cents"),
        )
        .where(Reimbursement.status == ReimbursementStatus.RECEIVED)
        .group_by(Reimbursement.transaction_id)
        .subquery()
    )

    # a transaction with no reimbursements has no matching row, so coalesce to zero
    received = func.coalesce(received_per_transaction.c.received_cents, 0)

    return (
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount_cents), 0),
            func.coalesce(func.sum(received), 0),
            func.coalesce(
                func.sum(func.greatest(0, Transaction.amount_cents - received)), 0
            ),
        )
        .select_from(Transaction)
        .outerjoin(
            received_per_transaction,
            received_per_transaction.c.transaction_id == Transaction.id,
        )
    )


async def _totals_between(session: AsyncSession, start: date, end: date) -> Totals:
    """Totals for a half-open date range, filtered on the transaction date.

    Reimbursements credit the month of the transaction, not the month the money arrived, so
    received_date never filters. Past months restate as reimbursements land.
    """
    stmt = _base_query().where(
        Transaction.txn_date >= start, Transaction.txn_date < end
    )
    row = (await session.execute(stmt)).one()
    return Totals(*row)


async def monthly_summary(session: AsyncSession, month: date) -> MonthlySummary:
    """Summary for the month `month` falls in."""
    month_start = month_start_of(month)
    start, end = month_bounds(month_start)
    totals = await _totals_between(session, start, end)
    goal = await session.get(MonthlyBudgetGoal, month_start)
    return _to_monthly(month_start, totals, goal.goal_cents if goal else None)


async def monthly_summaries_for_year(
    session: AsyncSession, year: int
) -> Sequence[MonthlySummary]:
    """Every month in the year that has transactions or a goal, oldest first."""
    start, end = year_bounds(year)
    month_column = func.date_trunc("month", Transaction.txn_date).cast(
        Transaction.txn_date.type
    )

    stmt = (
        _base_query()
        .add_columns(month_column.label("month_start"))
        .where(Transaction.txn_date >= start, Transaction.txn_date < end)
        .group_by(month_column)
    )
    rows = (await session.execute(stmt)).all()
    by_month = {row.month_start: Totals(*row[:4]) for row in rows}

    goals = {
        goal.month_start: goal.goal_cents
        for goal in await list_goals_for_year(session, year)
    }

    # a month with a goal but no spending still belongs in the list
    empty = Totals(0, 0, 0, 0)
    months = sorted(by_month.keys() | goals.keys())
    return [
        _to_monthly(month, by_month.get(month, empty), goals.get(month))
        for month in months
    ]


async def yearly_summary(session: AsyncSession, year: int) -> YearlySummary:
    """Derived from the months, since monthly goals are the source of truth."""
    start, end = year_bounds(year)
    totals = await _totals_between(session, start, end)
    goal_cents = sum(
        goal.goal_cents for goal in await list_goals_for_year(session, year)
    )

    return YearlySummary(
        year=year,
        transaction_count=totals.transaction_count,
        gross_cents=totals.gross_cents,
        received_cents=totals.received_cents,
        net_cents=totals.net_cents,
        goal_cents=goal_cents,
        variance_cents=goal_cents - totals.net_cents,
    )


def _to_monthly(
    month_start: date, totals: Totals, goal_cents: int | None
) -> MonthlySummary:
    return MonthlySummary(
        month_start=month_start,
        transaction_count=totals.transaction_count,
        gross_cents=totals.gross_cents,
        received_cents=totals.received_cents,
        net_cents=totals.net_cents,
        goal_cents=goal_cents,
        # no goal means no variance to report, rather than a misleading zero
        variance_cents=None if goal_cents is None else goal_cents - totals.net_cents,
    )
