"""Transaction template pages."""

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
from jyyfinhub_spendtracker.transaction_templates.schemas import (
    TransactionTemplateCreate,
    TransactionTemplateUpdate,
)
from jyyfinhub_spendtracker.transaction_templates.service import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)
from jyyfinhub_spendtracker.web.forms import checkbox, clean, field_errors, parse_amount
from jyyfinhub_spendtracker.web.templates import templates

router = APIRouter(include_in_schema=False)

TEMPLATES_URL = "/transaction-templates"
OPTIONAL_FIELDS = ("subcategory", "notes")


def _form_values(form: FormData) -> dict[str, Any]:
    """Normalise the template form.

    A blank amount means the amount varies, so it stays None rather than becoming an error.
    """
    data = clean(form, optional=OPTIONAL_FIELDS)
    data["is_subscription"] = checkbox(form, "is_subscription")
    data["is_active"] = checkbox(form, "is_active")
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
        "transaction_templates/form.html",
        {
            "values": values,
            "errors": errors,
            "action": action,
            "heading": heading,
            "categories": SPEND_CATEGORIES,
            "payment_methods": await list_payment_methods(session, is_active=True),
        },
        status_code=status_code,
    )


@router.get(TEMPLATES_URL, response_class=HTMLResponse)
async def templates_page(request: Request, session: SessionDep) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "transaction_templates/list.html",
        {"presets": await list_templates(session)},
    )


@router.get(f"{TEMPLATES_URL}/new", response_class=HTMLResponse)
async def new_template_page(request: Request, session: SessionDep) -> HTMLResponse:
    return await _render_form(
        request,
        session,
        values={"is_active": True},
        errors={},
        action=TEMPLATES_URL,
        heading="Add template",
    )


@router.post(TEMPLATES_URL)
async def create_template_form(request: Request, session: SessionDep) -> Response:
    values = _form_values(await request.form())

    try:
        payload = TransactionTemplateCreate(**values)
    except ValidationError as exc:
        return await _render_form(
            request,
            session,
            values=values,
            errors=field_errors(exc),
            action=TEMPLATES_URL,
            heading="Add template",
            status_code=422,
        )

    try:
        await create_template(session, payload)
    except SpendTrackerError as exc:
        return await _render_form(
            request,
            session,
            values=values,
            errors={"name": exc.message},
            action=TEMPLATES_URL,
            heading="Add template",
            status_code=exc.status_code,
        )

    await session.commit()
    return RedirectResponse(TEMPLATES_URL, status_code=HTTP_303_SEE_OTHER)


@router.get(TEMPLATES_URL + "/{template_id}/edit", response_class=HTMLResponse)
async def edit_template_page(
    request: Request, session: SessionDep, template_id: int
) -> HTMLResponse:
    preset = await get_template(session, template_id)
    return await _render_form(
        request,
        session,
        values={
            "name": preset.name,
            "merchant": preset.merchant,
            "category": preset.category,
            "subcategory": preset.subcategory,
            "amount": f"{preset.amount_cents / 100:.2f}"
            if preset.amount_cents is not None
            else "",
            "payment_method_id": preset.payment_method_id,
            "notes": preset.notes,
            "is_subscription": preset.is_subscription,
            "is_active": preset.is_active,
        },
        errors={},
        action=f"{TEMPLATES_URL}/{template_id}",
        heading=f"Edit {preset.name}",
    )


@router.post(TEMPLATES_URL + "/{template_id}")
async def update_template_form(
    request: Request, session: SessionDep, template_id: int
) -> Response:
    values = _form_values(await request.form())
    action = f"{TEMPLATES_URL}/{template_id}"

    try:
        payload = TransactionTemplateUpdate(**values)
    except ValidationError as exc:
        return await _render_form(
            request,
            session,
            values=values,
            errors=field_errors(exc),
            action=action,
            heading="Edit template",
            status_code=422,
        )

    try:
        await update_template(session, template_id, payload)
    except SpendTrackerError as exc:
        return await _render_form(
            request,
            session,
            values=values,
            errors={"name": exc.message},
            action=action,
            heading="Edit template",
            status_code=exc.status_code,
        )

    await session.commit()
    return RedirectResponse(TEMPLATES_URL, status_code=HTTP_303_SEE_OTHER)


@router.post(TEMPLATES_URL + "/{template_id}/delete")
async def delete_template_form(
    session: SessionDep, template_id: int
) -> RedirectResponse:
    """Transactions created from this template are unaffected."""
    await delete_template(session, template_id)
    await session.commit()
    return RedirectResponse(TEMPLATES_URL, status_code=HTTP_303_SEE_OTHER)
