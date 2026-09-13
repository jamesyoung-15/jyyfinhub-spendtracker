"""Monthly budget goal business logic, shared by the API, web routes, and CLI.

Services flush but never commit. The caller owns the transaction boundary.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.goals.exceptions import GoalNotFound
from jyyfinhub_spendtracker.goals.models import MonthlyBudgetGoal
from jyyfinhub_spendtracker.goals.schemas import MonthlyBudgetGoalUpsert


def month_start_of(day: date) -> date:
    """First of the month `day` falls in, which is the goal's primary key."""
    return day.replace(day=1)


async def find_goal(session: AsyncSession, month: date) -> MonthlyBudgetGoal | None:
    """Goal for a month, or None. Summaries use this, since a month may have no goal."""
    return await session.get(MonthlyBudgetGoal, month_start_of(month))


async def get_goal(session: AsyncSession, month: date) -> MonthlyBudgetGoal:
    """Goal for a month, or raise."""
    goal = await find_goal(session, month)
    if goal is None:
        raise GoalNotFound(month_start_of(month))
    return goal


async def list_goals_for_year(
    session: AsyncSession, year: int
) -> Sequence[MonthlyBudgetGoal]:
    """Every goal set in a year, oldest month first."""
    stmt = (
        select(MonthlyBudgetGoal)
        .where(
            MonthlyBudgetGoal.month_start >= date(year, 1, 1),
            MonthlyBudgetGoal.month_start < date(year + 1, 1, 1),
        )
        .order_by(MonthlyBudgetGoal.month_start)
    )
    return (await session.scalars(stmt)).all()


async def upsert_goal(
    session: AsyncSession, month: date, data: MonthlyBudgetGoalUpsert
) -> MonthlyBudgetGoal:
    """Set the goal for a month, replacing any existing one.

    PUT semantics: one goal per month, so setting it twice is not an error.
    """
    month_start = month_start_of(month)
    goal = await session.get(MonthlyBudgetGoal, month_start)

    if goal is None:
        goal = MonthlyBudgetGoal(month_start=month_start, **data.model_dump())
        session.add(goal)
    else:
        goal.goal_cents = data.goal_cents
        goal.notes = data.notes

    await session.flush()
    return goal
