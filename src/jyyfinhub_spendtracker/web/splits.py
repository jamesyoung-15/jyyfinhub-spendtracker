"""Split order pages.

A separate module so these routes can be registered before /transactions/{transaction_id},
which would otherwise match "split" as a path parameter and 422.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from starlette.datastructures import FormData
from starlette.status import HTTP_303_SEE_OTHER

from jyyfinhub_spendtracker.categories import SPEND_CATEGORIES
from jyyfinhub_spendtracker.core.exceptions import SpendTrackerError
from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.payment_methods.service import list_payment_methods
from jyyfinhub_spendtracker.transactions.schemas import TransactionSplitCreate
from jyyfinhub_spendtracker.transactions.service import (
    create_split,
    last_used_payment_method_id,
    recent_merchants,
)
from jyyfinhub_spendtracker.web.forms import checkbox, clean, parse_amount
from jyyfinhub_spendtracker.web.templates import templates

router = APIRouter(include_in_schema=False)


def _today() -> date:
    """Local date, not UTC. The container sets TZ."""
    return date.today()  # noqa: DTZ011


SPLIT_URL = "/transactions/split"
SPLIT_ROWS = 5


def _split_allocations(form: FormData) -> list[dict[str, Any]]:
    """Collect the filled-in allocation rows, ignoring blanks."""
    rows: list[dict[str, Any]] = []
    for index in range(SPLIT_ROWS):
        category = str(form.get(f"category_{index}") or "").strip()
        amount = str(form.get(f"amount_{index}") or "").strip()
        if not category and not amount:
            continue
        rows.append(
            {
                "category": category,
                "subcategory": str(form.get(f"subcategory_{index}") or "").strip()
                or None,
                "amount_cents": parse_amount(amount),
                "amount": amount,
                "notes": str(form.get(f"notes_{index}") or "").strip() or None,
            }
        )
    return rows


async def _render_split_form(
    request: Request,
    session: SessionDep,
    *,
    values: dict[str, Any],
    allocations: list[dict[str, Any]],
    errors: dict[str, str],
    status_code: int = 200,
) -> HTMLResponse:
    # pad so the form always offers empty rows to fill
    padded = allocations + [{} for _ in range(SPLIT_ROWS - len(allocations))]
    return templates.TemplateResponse(
        request,
        "transactions/split.html",
        {
            "values": values,
            "allocations": padded[:SPLIT_ROWS],
            "errors": errors,
            "categories": SPEND_CATEGORIES,
            "payment_methods": await list_payment_methods(session),
            "merchants": await recent_merchants(session),
        },
        status_code=status_code,
    )


@router.get(SPLIT_URL, response_class=HTMLResponse)
async def new_split_page(request: Request, session: SessionDep) -> HTMLResponse:
    return await _render_split_form(
        request,
        session,
        values={
            "txn_date": _today().isoformat(),
            "payment_method_id": await last_used_payment_method_id(session),
        },
        allocations=[],
        errors={},
    )


@router.post(SPLIT_URL)
async def create_split_form(request: Request, session: SessionDep) -> Response:
    form = await request.form()
    values = clean(form, optional=())
    allocations = _split_allocations(form)
    values["is_subscription"] = checkbox(form, "is_subscription")

    payload_data = {
        "txn_date": values.get("txn_date"),
        "merchant": values.get("merchant"),
        "payment_method_id": values.get("payment_method_id"),
        "is_subscription": values["is_subscription"],
        "allocations": [
            {k: v for k, v in row.items() if k != "amount"} for row in allocations
        ],
    }

    try:
        payload = TransactionSplitCreate(**payload_data)
    except ValidationError as exc:
        return await _render_split_form(
            request,
            session,
            values=values,
            allocations=allocations,
            errors=_split_errors(exc),
            status_code=422,
        )

    try:
        await create_split(session, payload)
    except SpendTrackerError as exc:
        return await _render_split_form(
            request,
            session,
            values=values,
            allocations=allocations,
            errors={"allocations": exc.message},
            status_code=exc.status_code,
        )

    await session.commit()
    return RedirectResponse(SPLIT_URL, status_code=HTTP_303_SEE_OTHER)


def _split_errors(exc: ValidationError) -> dict[str, str]:
    """Flatten, collapsing per-allocation errors under one key for display above the rows."""
    errors: dict[str, str] = {}
    for error in exc.errors():
        location = error["loc"]
        key = "allocations" if location and location[0] == "allocations" else None
        field = key or (str(location[0]) if location else "_")
        errors.setdefault(field, error["msg"])
    return errors
