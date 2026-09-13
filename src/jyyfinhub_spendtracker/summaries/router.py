from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path

from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.summaries.schemas import MonthlySummary, YearlySummary
from jyyfinhub_spendtracker.summaries.service import (
    monthly_summaries_for_year,
    monthly_summary,
    yearly_summary,
)

router = APIRouter(prefix="/summaries", tags=["summaries"])

MonthPath = Annotated[
    str, Path(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM", examples=["2026-09"])
]


@router.get("/monthly/{month}", response_model=MonthlySummary)
async def read_monthly_summary(session: SessionDep, month: MonthPath) -> MonthlySummary:
    return await monthly_summary(session, date.fromisoformat(f"{month}-01"))


@router.get("/yearly/{year}", response_model=YearlySummary)
async def read_yearly_summary(session: SessionDep, year: int) -> YearlySummary:
    return await yearly_summary(session, year)


@router.get("/yearly/{year}/months", response_model=list[MonthlySummary])
async def read_months_in_year(
    session: SessionDep, year: int
) -> Sequence[MonthlySummary]:
    return await monthly_summaries_for_year(session, year)
