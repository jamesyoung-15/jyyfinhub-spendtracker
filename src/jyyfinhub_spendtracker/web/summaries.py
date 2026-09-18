"""Summary pages. The goal form lives here, since a goal only means something next to spend."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from starlette.status import HTTP_303_SEE_OTHER

from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.goals.schemas import MonthlyBudgetGoalUpsert
from jyyfinhub_spendtracker.goals.service import upsert_goal
from jyyfinhub_spendtracker.summaries.service import (
    monthly_categories,
    monthly_summaries_for_year,
    monthly_summary,
    yearly_categories,
    yearly_summary,
)
from jyyfinhub_spendtracker.web.forms import clean, field_errors, parse_amount
from jyyfinhub_spendtracker.web.templates import templates

router = APIRouter(include_in_schema=False)

SUMMARY_URL = "/summary"


def _today() -> date:
    """Local date, not UTC. The container sets TZ."""
    return date.today()  # noqa: DTZ011


async def _render(
    request: Request,
    session: SessionDep,
    month: date,
    *,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    summary = await monthly_summary(session, month)
    return templates.TemplateResponse(
        request,
        "summaries/month.html",
        {
            "summary": summary,
            "month": month.strftime("%Y-%m"),
            "month_label": month.strftime("%B %Y"),
            "year": month.year,
            "categories": await monthly_categories(session, month),
            "yearly": await yearly_summary(session, month.year),
            "yearly_categories": await yearly_categories(session, month.year),
            "months": await monthly_summaries_for_year(session, month.year),
            "errors": errors or {},
        },
        status_code=status_code,
    )


@router.get(SUMMARY_URL, response_class=HTMLResponse)
async def summary_page(
    request: Request, session: SessionDep, month: str | None = None
) -> HTMLResponse:
    selected = date.fromisoformat(f"{month}-01") if month else _today().replace(day=1)
    return await _render(request, session, selected)


@router.post(SUMMARY_URL + "/{month}/goal")
async def set_goal_form(request: Request, session: SessionDep, month: str) -> Response:
    selected = date.fromisoformat(f"{month}-01")
    values: dict[str, Any] = clean(await request.form(), optional=("notes",))
    values["goal_cents"] = parse_amount(values.pop("goal", None))

    try:
        payload = MonthlyBudgetGoalUpsert(**values)
    except ValidationError as exc:
        return await _render(
            request, session, selected, errors=field_errors(exc), status_code=422
        )

    await upsert_goal(session, selected, payload)
    await session.commit()
    return RedirectResponse(
        f"{SUMMARY_URL}?month={month}", status_code=HTTP_303_SEE_OTHER
    )
