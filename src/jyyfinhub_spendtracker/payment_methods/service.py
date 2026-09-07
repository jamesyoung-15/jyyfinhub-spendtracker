"""Payment method business logic, shared by the API, web routes, and CLI.

Services flush but never commit. The caller owns the transaction boundary, so several service calls
can make up one atomic unit of work.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.exceptions import (
    PaymentMethodInUse,
    PaymentMethodNameTaken,
    PaymentMethodNotFound,
)
from jyyfinhub_spendtracker.payment_methods.models import (
    PaymentMethod,
    PaymentMethodKind,
)
from jyyfinhub_spendtracker.payment_methods.schemas import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
)


async def get_payment_method(session: AsyncSession, payment_id: int) -> PaymentMethod:
    """Get a single payment method by ID"""
    payment_method = await session.get(PaymentMethod, payment_id)
    if payment_method is None:
        raise PaymentMethodNotFound(payment_id)
    return payment_method


async def list_payment_methods(
    session: AsyncSession,
    *,
    kind: PaymentMethodKind | None = None,
    is_active: bool | None = None,
    expires_from: date | None = None,
    expires_before: date | None = None,
    include_never_expires: bool = False,
) -> Sequence[PaymentMethod]:
    """Get list of payment methods with filter options.

    `expires_on` is nullable and NULL fails every comparison, so a date filter drops cards that
    never expire unless `include_never_expires` is set.
    """
    stmt = select(PaymentMethod).order_by(PaymentMethod.name)

    if kind is not None:
        stmt = stmt.where(PaymentMethod.kind == kind)
    if is_active is not None:
        stmt = stmt.where(PaymentMethod.is_active == is_active)

    if expires_from is not None:
        condition = PaymentMethod.expires_on >= expires_from
        if include_never_expires:
            condition = or_(condition, PaymentMethod.expires_on.is_(None))
        stmt = stmt.where(condition)

    if expires_before is not None:
        condition = PaymentMethod.expires_on < expires_before
        if include_never_expires:
            condition = or_(condition, PaymentMethod.expires_on.is_(None))
        stmt = stmt.where(condition)

    return (await session.scalars(stmt)).all()


async def create_payment_method(
    session: AsyncSession, data: PaymentMethodCreate
) -> PaymentMethod:
    """Create a payment method"""
    payment_method = PaymentMethod(**data.model_dump())
    session.add(payment_method)

    # uq_payment_methods_name is the only unique constraint on this table
    try:
        await session.flush()
    except IntegrityError as exc:
        raise PaymentMethodNameTaken(data.name) from exc

    return payment_method


async def update_payment_method(
    session: AsyncSession, payment_id: int, data: PaymentMethodUpdate
) -> PaymentMethod:
    """Update existing payment method data.

    Set `is_active` to false here to retire a card rather than deleting it.
    """
    payment_method = await get_payment_method(session, payment_id)

    # exclude_unset distinguishes an omitted field from one explicitly set to null
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(payment_method, field, value)

    try:
        await session.flush()
    except IntegrityError as exc:
        raise PaymentMethodNameTaken(changes.get("name", "")) from exc

    return payment_method


async def delete_payment_method(session: AsyncSession, payment_id: int) -> None:
    """Delete a payment method that has never been used.

    Transactions reference payment methods with ON DELETE RESTRICT, so a card with any history
    cannot be removed. Retire it with `is_active` instead.
    """
    payment_method = await get_payment_method(session, payment_id)
    await session.delete(payment_method)

    try:
        await session.flush()
    except IntegrityError as exc:
        raise PaymentMethodInUse(payment_id) from exc
