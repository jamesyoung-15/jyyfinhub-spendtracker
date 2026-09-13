from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.goals import service
from jyyfinhub_spendtracker.goals.exceptions import GoalNotFound
from jyyfinhub_spendtracker.goals.schemas import MonthlyBudgetGoalUpsert

SEPTEMBER = date(2026, 9, 1)


async def test_get_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(GoalNotFound):
        await service.get_goal(session, SEPTEMBER)


async def test_find_missing_returns_none(session: AsyncSession) -> None:
    """Summaries need this: a month with no goal is normal, not an error"""
    assert await service.find_goal(session, SEPTEMBER) is None


async def test_upsert_creates(session: AsyncSession) -> None:
    goal = await service.upsert_goal(
        session, SEPTEMBER, MonthlyBudgetGoalUpsert(goal_cents=250000)
    )
    assert goal.month_start == SEPTEMBER
    assert goal.goal_cents == 250000


async def test_upsert_is_idempotent(session: AsyncSession) -> None:
    """PUT semantics: one goal per month, so setting it twice replaces rather than conflicts"""
    await service.upsert_goal(
        session, SEPTEMBER, MonthlyBudgetGoalUpsert(goal_cents=250000)
    )
    updated = await service.upsert_goal(
        session, SEPTEMBER, MonthlyBudgetGoalUpsert(goal_cents=300000, notes="raised")
    )

    assert updated.goal_cents == 300000
    assert updated.notes == "raised"
    assert len(await service.list_goals_for_year(session, 2026)) == 1


async def test_any_day_normalises_to_first(session: AsyncSession) -> None:
    """The PK is the first of the month, so the service normalises before touching the db"""
    goal = await service.upsert_goal(
        session, date(2026, 9, 23), MonthlyBudgetGoalUpsert(goal_cents=1000)
    )
    assert goal.month_start == SEPTEMBER

    # and a lookup by any other day in that month finds it
    assert await service.find_goal(session, date(2026, 9, 4)) is not None


async def test_zero_goal_allowed(session: AsyncSession) -> None:
    goal = await service.upsert_goal(
        session, SEPTEMBER, MonthlyBudgetGoalUpsert(goal_cents=0)
    )
    assert goal.goal_cents == 0


async def test_negative_goal_rejected() -> None:
    with pytest.raises(ValueError):
        MonthlyBudgetGoalUpsert(goal_cents=-1)


async def test_list_for_year_excludes_neighbours(session: AsyncSession) -> None:
    for month in (
        date(2025, 12, 1),
        date(2026, 1, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
    ):
        await service.upsert_goal(
            session, month, MonthlyBudgetGoalUpsert(goal_cents=100)
        )

    found = await service.list_goals_for_year(session, 2026)
    assert [g.month_start for g in found] == [date(2026, 1, 1), date(2026, 12, 1)]
