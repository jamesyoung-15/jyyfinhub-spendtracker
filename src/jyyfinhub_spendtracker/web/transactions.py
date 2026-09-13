"""Transaction pages. The entry form is the surface that has to be fast."""

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
from jyyfinhub_spendtracker.transactions.schemas import (
    TransactionCreate,
    TransactionUpdate,
)
from jyyfinhub_spendtracker.transactions.service import (
    create_transaction,
    delete_transaction,
    get_transaction,
    last_used_payment_method_id,
    list_transactions,
    recent_merchants,
    update_transaction,
)
from jyyfinhub_spendtracker.web.forms import checkbox, clean, field_errors, parse_amount
from jyyfinhub_spendtracker.web.templates import templates

router = APIRouter(include_in_schema=False)

TRANSACTIONS_URL = "/transactions"
OPTIONAL_FIELDS = ("subcategory", "notes")


def _today() -> date:
    """Local date, not UTC.

    The container sets TZ, otherwise an evening entry would default to tomorrow.
    """
    return date.today()  # noqa: DTZ011


def _form_values(form: FormData) -> dict[str, Any]:
    """Normalise the transaction form.

    The form collects dollars because that is what a receipt shows; storage is integer cents.
    """
    data = clean(form, optional=OPTIONAL_FIELDS)
    data["is_subscription"] = checkbox(form, "is_subscription")
    data["amount_cents"] = parse_amount(data.pop("amount", None))
    return data


async def _render_form(
    request: Request,
    session: SessionDep,
    *,
    values: dict[str, Any],
    errors: dict[str, str],
    action: str,
    heading: str,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "transactions/form.html",
        {
            "values": values,
            "errors": errors,
            "action": action,
            "heading": heading,
            "categories": SPEND_CATEGORIES,
            "payment_methods": await list_payment_methods(session, is_active=True),
            "merchants": await recent_merchants(session),
        },
        status_code=status_code,
    )


@router.get(TRANSACTIONS_URL, response_class=HTMLResponse)
async def transactions_page(
    request: Request, session: SessionDep, month: str | None = None
) -> HTMLResponse:
    selected = date.fromisoformat(f"{month}-01") if month else _today()
    return templates.TemplateResponse(
        request,
        "transactions/list.html",
        {
            "transactions": await list_transactions(session, month=selected),
            "month": selected.strftime("%Y-%m"),
            "month_label": selected.strftime("%B %Y"),
        },
    )


@router.get(f"{TRANSACTIONS_URL}/new", response_class=HTMLResponse)
async def new_transaction_page(request: Request, session: SessionDep) -> HTMLResponse:
    return await _render_form(
        request,
        session,
        # smart defaults: today, and whichever card was used last
        values={
            "txn_date": _today().isoformat(),
            "payment_method_id": await last_used_payment_method_id(session),
        },
        errors={},
        action=TRANSACTIONS_URL,
        heading="Add transaction",
    )


@router.post(TRANSACTIONS_URL)
async def create_transaction_form(request: Request, session: SessionDep) -> Response:
    values = _form_values(await request.form())

    try:
        payload = TransactionCreate(**values)
    except ValidationError as exc:
        return await _render_form(
            request,
            session,
            values=values,
            errors=field_errors(exc),
            action=TRANSACTIONS_URL,
            heading="Add transaction",
            status_code=422,
        )

    try:
        await create_transaction(session, payload)
    except SpendTrackerError as exc:
        # an invalid category pair or a missing card is the user's to fix, so stay on the form
        return await _render_form(
            request,
            session,
            values=values,
            errors={"category": exc.message},
            action=TRANSACTIONS_URL,
            heading="Add transaction",
            status_code=exc.status_code,
        )

    await session.commit()
    # back to a blank form, since entering one transaction usually means entering several
    return RedirectResponse(f"{TRANSACTIONS_URL}/new", status_code=HTTP_303_SEE_OTHER)


@router.get(TRANSACTIONS_URL + "/{transaction_id}/edit", response_class=HTMLResponse)
async def edit_transaction_page(
    request: Request, session: SessionDep, transaction_id: int
) -> HTMLResponse:
    transaction = await get_transaction(session, transaction_id)
    return await _render_form(
        request,
        session,
        values={
            "txn_date": transaction.txn_date.isoformat(),
            "merchant": transaction.merchant,
            "category": transaction.category,
            "subcategory": transaction.subcategory,
            "amount": f"{transaction.amount_cents / 100:.2f}",
            "payment_method_id": transaction.payment_method_id,
            "notes": transaction.notes,
            "is_subscription": transaction.is_subscription,
        },
        errors={},
        action=f"{TRANSACTIONS_URL}/{transaction_id}",
        heading="Edit transaction",
    )


@router.post(TRANSACTIONS_URL + "/{transaction_id}")
async def update_transaction_form(
    request: Request, session: SessionDep, transaction_id: int
) -> Response:
    values = _form_values(await request.form())
    action = f"{TRANSACTIONS_URL}/{transaction_id}"

    try:
        payload = TransactionUpdate(**values)
    except ValidationError as exc:
        return await _render_form(
            request,
            session,
            values=values,
            errors=field_errors(exc),
            action=action,
            heading="Edit transaction",
            status_code=422,
        )

    try:
        await update_transaction(session, transaction_id, payload)
    except SpendTrackerError as exc:
        return await _render_form(
            request,
            session,
            values=values,
            errors={"category": exc.message},
            action=action,
            heading="Edit transaction",
            status_code=exc.status_code,
        )

    await session.commit()
    return RedirectResponse(TRANSACTIONS_URL, status_code=HTTP_303_SEE_OTHER)


@router.post(TRANSACTIONS_URL + "/{transaction_id}/delete")
async def delete_transaction_form(
    session: SessionDep, transaction_id: int
) -> RedirectResponse:
    await delete_transaction(session, transaction_id)
    await session.commit()
    return RedirectResponse(TRANSACTIONS_URL, status_code=HTTP_303_SEE_OTHER)
