"""HTML pages. Thin wrappers over the same services the API uses.

HTML forms only support GET and POST, so updates and deletes are POSTs to sub-paths rather than
PATCH and DELETE.
"""

from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from starlette.datastructures import FormData
from starlette.status import HTTP_303_SEE_OTHER

from jyyfinhub_spendtracker.core.exceptions import ConflictError
from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethodKind
from jyyfinhub_spendtracker.payment_methods.schemas import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
)
from jyyfinhub_spendtracker.payment_methods.service import (
    create_payment_method,
    delete_payment_method,
    get_payment_method,
    list_payment_methods,
    update_payment_method,
)
from jyyfinhub_spendtracker.web.templates import templates

# these render HTML, so they have no place in the OpenAPI schema
router = APIRouter(include_in_schema=False)

PAYMENT_METHODS_URL = "/payment-methods"
OPTIONAL_TEXT_FIELDS = ("expires_on", "notes")


def _form_values(form: FormData) -> dict[str, Any]:
    """Turn raw form data into something the Pydantic schemas accept."""
    data: dict[str, Any] = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in form.items()
    }

    # a blank input posts "" but the schemas want None
    for field in OPTIONAL_TEXT_FIELDS:
        if data.get(field) == "":
            data[field] = None

    # an unchecked checkbox is absent from the payload entirely, so absence means False
    data["is_active"] = "is_active" in form
    return data


def _field_errors(exc: ValidationError) -> dict[str, str]:
    """Flatten Pydantic errors to one message per field for display next to the input."""
    errors: dict[str, str] = {}
    for error in exc.errors():
        field = str(error["loc"][0]) if error["loc"] else "_"
        errors.setdefault(field, error["msg"])
    return errors


def _render_form(
    request: Request,
    *,
    values: dict[str, Any],
    errors: dict[str, str],
    action: str,
    heading: str,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "payment_methods/form.html",
        {
            "values": values,
            "errors": errors,
            "action": action,
            "heading": heading,
            "kinds": list(PaymentMethodKind),
        },
        status_code=status_code,
    )


@router.get("/")
async def home() -> RedirectResponse:
    return RedirectResponse(PAYMENT_METHODS_URL, status_code=HTTP_303_SEE_OTHER)


@router.get(PAYMENT_METHODS_URL, response_class=HTMLResponse)
async def payment_methods_page(request: Request, session: SessionDep) -> HTMLResponse:
    payment_methods = await list_payment_methods(session)
    return templates.TemplateResponse(
        request,
        "payment_methods/list.html",
        {"payment_methods": payment_methods},
    )


@router.get(f"{PAYMENT_METHODS_URL}/new", response_class=HTMLResponse)
async def new_payment_method_page(request: Request) -> HTMLResponse:
    return _render_form(
        request,
        values={"is_active": True, "kind": PaymentMethodKind.CREDIT},
        errors={},
        action=PAYMENT_METHODS_URL,
        heading="Add payment method",
    )


@router.post(PAYMENT_METHODS_URL)
async def create_payment_method_form(request: Request, session: SessionDep) -> Response:
    values = _form_values(await request.form())

    try:
        payload = PaymentMethodCreate(**values)
    except ValidationError as exc:
        # re-render with what they typed, rather than the API's 422 JSON
        return _render_form(
            request,
            values=values,
            errors=_field_errors(exc),
            action=PAYMENT_METHODS_URL,
            heading="Add payment method",
            status_code=422,
        )

    try:
        await create_payment_method(session, payload)
    except ConflictError as exc:
        # a duplicate name is the user's to fix, so keep them on the form
        return _render_form(
            request,
            values=values,
            errors={"name": exc.message},
            action=PAYMENT_METHODS_URL,
            heading="Add payment method",
            status_code=409,
        )

    await session.commit()
    return RedirectResponse(PAYMENT_METHODS_URL, status_code=HTTP_303_SEE_OTHER)


@router.get(PAYMENT_METHODS_URL + "/{payment_id}/edit", response_class=HTMLResponse)
async def edit_payment_method_page(
    request: Request, session: SessionDep, payment_id: int
) -> HTMLResponse:
    payment_method = await get_payment_method(session, payment_id)
    return _render_form(
        request,
        values={
            "name": payment_method.name,
            "kind": payment_method.kind,
            "is_active": payment_method.is_active,
            "expires_on": payment_method.expires_on,
            "notes": payment_method.notes,
        },
        errors={},
        action=f"{PAYMENT_METHODS_URL}/{payment_id}",
        heading=f"Edit {payment_method.name}",
    )


@router.post(PAYMENT_METHODS_URL + "/{payment_id}")
async def update_payment_method_form(
    request: Request, session: SessionDep, payment_id: int
) -> Response:
    values = _form_values(await request.form())
    action = f"{PAYMENT_METHODS_URL}/{payment_id}"

    try:
        payload = PaymentMethodUpdate(**values)
    except ValidationError as exc:
        return _render_form(
            request,
            values=values,
            errors=_field_errors(exc),
            action=action,
            heading="Edit payment method",
            status_code=422,
        )

    try:
        await update_payment_method(session, payment_id, payload)
    except ConflictError as exc:
        return _render_form(
            request,
            values=values,
            errors={"name": exc.message},
            action=action,
            heading="Edit payment method",
            status_code=409,
        )

    await session.commit()
    return RedirectResponse(PAYMENT_METHODS_URL, status_code=HTTP_303_SEE_OTHER)


@router.post(PAYMENT_METHODS_URL + "/{payment_id}/delete")
async def delete_payment_method_form(
    session: SessionDep, payment_id: int
) -> RedirectResponse:
    """Only works for a card with no transactions; otherwise the error page explains why."""
    await delete_payment_method(session, payment_id)
    await session.commit()
    return RedirectResponse(PAYMENT_METHODS_URL, status_code=HTTP_303_SEE_OTHER)
