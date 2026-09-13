from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path

from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.goals.models import MonthlyBudgetGoal
from jyyfinhub_spendtracker.goals.schemas import (
    MonthlyBudgetGoalRead,
    MonthlyBudgetGoalUpsert,
)
from jyyfinhub_spendtracker.goals.service import (
    get_goal,
    list_goals_for_year,
    upsert_goal,
)

router = APIRouter(prefix="/goals", tags=["goals"])

MonthPath = Annotated[
    str, Path(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM", examples=["2026-09"])
]


def _to_date(month: str) -> date:
    """The path pattern guarantees this parses, so the service takes a real date."""
    return date.fromisoformat(f"{month}-01")


@router.get("/monthly", response_model=list[MonthlyBudgetGoalRead])
async def read_goals_for_year(
    session: SessionDep, year: int
) -> Sequence[MonthlyBudgetGoal]:
    return await list_goals_for_year(session, year)


@router.get("/monthly/{month}", response_model=MonthlyBudgetGoalRead)
async def read_goal(session: SessionDep, month: MonthPath) -> MonthlyBudgetGoal:
    return await get_goal(session, _to_date(month))


@router.put("/monthly/{month}", response_model=MonthlyBudgetGoalRead)
async def set_goal(
    session: SessionDep, month: MonthPath, data: MonthlyBudgetGoalUpsert
) -> MonthlyBudgetGoal:
    """Idempotent: one goal per month, so setting it twice replaces rather than conflicts."""
    goal = await upsert_goal(session, _to_date(month), data)
    await session.commit()
    return goal
