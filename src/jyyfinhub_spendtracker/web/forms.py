"""Helpers for turning raw HTML form data into something the Pydantic schemas accept."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from starlette.datastructures import FormData


def clean(form: FormData, *, optional: tuple[str, ...] = ()) -> dict[str, Any]:
    """Strip strings and turn blank optional inputs into None.

    A blank input posts "" which fails date and int parsing, but the schemas want None.
    """
    data: dict[str, Any] = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in form.items()
    }
    for field in optional:
        if data.get(field) == "":
            data[field] = None
    return data


def checkbox(form: FormData, field: str) -> bool:
    """An unchecked box is absent from the payload entirely, so absence means False."""
    return field in form


def dollars_to_cents(value: str) -> int:
    """Parse a dollar amount into integer cents.

    Decimal rather than float, so 43.18 cannot arrive as 4317.999999.
    """
    cents = (Decimal(value) * 100).to_integral_value(rounding=ROUND_HALF_UP)
    return int(cents)


def parse_amount(value: Any) -> int | None:
    """Return cents, or None when the input is blank or not a number."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return dollars_to_cents(value)
    except (InvalidOperation, ValueError):
        return None


def field_errors(exc: ValidationError) -> dict[str, str]:
    """Flatten Pydantic errors to one message per field, for display beside the input."""
    errors: dict[str, str] = {}
    for error in exc.errors():
        field = str(error["loc"][0]) if error["loc"] else "_"
        errors.setdefault(field, error["msg"])
    return errors
