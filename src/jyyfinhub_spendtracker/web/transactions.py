"""Transaction pages. The entry form is the surface that has to be fast."""

from collections.abc import Sequence
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
from jyyfinhub_spendtracker.transaction_templates.models import TransactionTemplate
from jyyfinhub_spendtracker.transaction_templates.service import (
    get_template,
    list_templates,
)
from jyyfinhub_spendtracker.transactions.models import (
    ReimbursementSource,
    ReimbursementStatus,
)
from jyyfinhub_spendtracker.transactions.schemas import (
    ReimbursementCreate,
    ReimbursementUpdate,
    TransactionCreate,
    TransactionUpdate,
)
from jyyfinhub_spendtracker.transactions.service import (
    create_reimbursement,
    create_transaction,
    delete_reimbursement,
    delete_transaction,
    get_reimbursement,
    get_transaction,
    last_used_payment_method_id,
    list_transactions,
    recent_merchants,
    update_reimbursement,
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
    presets: Sequence[TransactionTemplate] = (),
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
            "presets": presets,
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
async def new_transaction_page(
    request: Request, session: SessionDep, template: int | None = None
) -> HTMLResponse:
    # smart defaults: today, and whichever card was used last
    values: dict[str, Any] = {
        "txn_date": _today().isoformat(),
        "payment_method_id": await last_used_payment_method_id(session),
    }

    if template is not None:
        # a template only fills the form in; nothing is saved until Save is pressed
        preset = await get_template(session, template)
        values |= {
            "merchant": preset.merchant,
            "category": preset.category,
            "subcategory": preset.subcategory,
            "amount": f"{preset.amount_cents / 100:.2f}"
            if preset.amount_cents is not None
            else "",
            "payment_method_id": preset.payment_method_id,
            "notes": preset.notes,
            "is_subscription": preset.is_subscription,
        }

    return await _render_form(
        request,
        session,
        values=values,
        errors={},
        action=TRANSACTIONS_URL,
        heading="Add transaction",
        presets=await list_templates(session, is_active=True),
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


# reimbursements live on the transaction detail page: rare enough (~1/month) that they should
# not crowd the entry or list pages, and the detail page is where split siblings will go too
REIMBURSEMENTS_URL = "/reimbursements"
REIMBURSEMENT_OPTIONAL_FIELDS = ("received_date", "notes")


def _reimbursement_values(form: FormData) -> dict[str, Any]:
    """Normalise a reimbursement form, which may be partial.

    Only touch amount_cents when the form actually carried an amount. Always writing the key
    would make exclude_unset treat it as an explicit null, so the inline "mark received" form
    would wipe the stored amount.
    """
    data = clean(form, optional=REIMBURSEMENT_OPTIONAL_FIELDS)
    if "amount" in data:
        data["amount_cents"] = parse_amount(data.pop("amount"))
    return data


async def _render_detail(
    request: Request,
    session: SessionDep,
    transaction_id: int,
    *,
    errors: dict[str, str] | None = None,
    values: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    transaction = await get_transaction(session, transaction_id)
    return templates.TemplateResponse(
        request,
        "transactions/detail.html",
        {
            # get_transaction eager-loads reimbursements, so the model properties work here
            # and no extra queries are needed
            "txn": transaction,
            "reimbursements": transaction.reimbursements,
            "received_cents": transaction.received_cents,
            "net_cents": transaction.net_cents,
            "sources": list(ReimbursementSource),
            "statuses": list(ReimbursementStatus),
            "values": values or {},
            "errors": errors or {},
        },
        status_code=status_code,
    )


@router.get(TRANSACTIONS_URL + "/{transaction_id}", response_class=HTMLResponse)
async def transaction_detail_page(
    request: Request, session: SessionDep, transaction_id: int
) -> HTMLResponse:
    return await _render_detail(request, session, transaction_id)


@router.post(TRANSACTIONS_URL + "/{transaction_id}/reimbursements")
async def add_reimbursement_form(
    request: Request, session: SessionDep, transaction_id: int
) -> Response:
    values = _reimbursement_values(await request.form())

    try:
        payload = ReimbursementCreate(**values)
    except ValidationError as exc:
        return await _render_detail(
            request,
            session,
            transaction_id,
            errors=field_errors(exc),
            values=values,
            status_code=422,
        )

    try:
        await create_reimbursement(session, transaction_id, payload)
    except SpendTrackerError as exc:
        return await _render_detail(
            request,
            session,
            transaction_id,
            errors={"status": exc.message},
            values=values,
            status_code=exc.status_code,
        )

    await session.commit()
    return RedirectResponse(
        f"{TRANSACTIONS_URL}/{transaction_id}", status_code=HTTP_303_SEE_OTHER
    )


@router.post(REIMBURSEMENTS_URL + "/{reimbursement_id}")
async def update_reimbursement_form(
    request: Request, session: SessionDep, reimbursement_id: int
) -> Response:
    reimbursement = await get_reimbursement(session, reimbursement_id)
    transaction_id = reimbursement.transaction_id
    values = _reimbursement_values(await request.form())

    try:
        payload = ReimbursementUpdate(**values)
    except ValidationError as exc:
        return await _render_detail(
            request,
            session,
            transaction_id,
            errors=field_errors(exc),
            status_code=422,
        )

    try:
        await update_reimbursement(session, reimbursement_id, payload)
    except SpendTrackerError as exc:
        return await _render_detail(
            request,
            session,
            transaction_id,
            errors={"status": exc.message},
            status_code=exc.status_code,
        )

    await session.commit()
    return RedirectResponse(
        f"{TRANSACTIONS_URL}/{transaction_id}", status_code=HTTP_303_SEE_OTHER
    )


@router.post(REIMBURSEMENTS_URL + "/{reimbursement_id}/delete")
async def delete_reimbursement_form(
    session: SessionDep, reimbursement_id: int
) -> RedirectResponse:
    reimbursement = await get_reimbursement(session, reimbursement_id)
    transaction_id = reimbursement.transaction_id

    await delete_reimbursement(session, reimbursement_id)
    await session.commit()
    return RedirectResponse(
        f"{TRANSACTIONS_URL}/{transaction_id}", status_code=HTTP_303_SEE_OTHER
    )
