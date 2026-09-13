"""Transaction template business logic, shared by the API, web routes, and CLI.

Services flush but never commit. The caller owns the transaction boundary.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jyyfinhub_spendtracker.categories import InvalidCategoryPair, is_valid_pair
from jyyfinhub_spendtracker.payment_methods.service import get_payment_method
from jyyfinhub_spendtracker.transaction_templates.exceptions import (
    TransactionTemplateNameTaken,
    TransactionTemplateNotFound,
)
from jyyfinhub_spendtracker.transaction_templates.models import TransactionTemplate
from jyyfinhub_spendtracker.transaction_templates.schemas import (
    TransactionTemplateCreate,
    TransactionTemplateUpdate,
)


async def _validate(
    session: AsyncSession,
    category: str,
    subcategory: str | None,
    payment_method_id: int,
) -> None:
    """Same rules a transaction gets, so a template cannot produce an invalid one."""
    if not is_valid_pair(category, subcategory):
        raise InvalidCategoryPair(category, subcategory)
    await get_payment_method(session, payment_method_id)


async def get_template(session: AsyncSession, template_id: int) -> TransactionTemplate:
    """Get a single template by ID, with its payment method loaded."""
    stmt = (
        select(TransactionTemplate)
        .where(TransactionTemplate.id == template_id)
        .options(selectinload(TransactionTemplate.payment_method))
    )
    template = await session.scalar(stmt)
    if template is None:
        raise TransactionTemplateNotFound(template_id)
    return template


async def list_templates(
    session: AsyncSession, *, is_active: bool | None = None
) -> Sequence[TransactionTemplate]:
    """List templates by name, with payment methods eager-loaded."""
    stmt = (
        select(TransactionTemplate)
        .options(selectinload(TransactionTemplate.payment_method))
        .order_by(TransactionTemplate.name)
    )
    if is_active is not None:
        stmt = stmt.where(TransactionTemplate.is_active == is_active)
    return (await session.scalars(stmt)).all()


async def create_template(
    session: AsyncSession, data: TransactionTemplateCreate
) -> TransactionTemplate:
    """Create a template."""
    await _validate(session, data.category, data.subcategory, data.payment_method_id)

    template = TransactionTemplate(**data.model_dump())

    # uq_transaction_templates_name is the only unique constraint on this table
    # the mutation must happen inside the SAVEPOINT. an object changed outside it belongs to the
    # outer unit of work, so a failed flush poisons the whole session rather than just the savepoint
    try:
        async with session.begin_nested():
            session.add(template)
    except IntegrityError as exc:
        raise TransactionTemplateNameTaken(data.name) from exc

    await session.refresh(template, ["payment_method"])
    return template


async def update_template(
    session: AsyncSession, template_id: int, data: TransactionTemplateUpdate
) -> TransactionTemplate:
    """Update a template, validating the state it ends up in.

    Editing a template never touches transactions already created from it.
    """
    template = await get_template(session, template_id)
    changes = data.model_dump(exclude_unset=True)

    # validate the merged result, since a partial update may send only subcategory
    await _validate(
        session,
        changes.get("category", template.category),
        changes.get("subcategory", template.subcategory),
        changes.get("payment_method_id", template.payment_method_id),
    )

    try:
        async with session.begin_nested():
            for field, value in changes.items():
                setattr(template, field, value)
    except IntegrityError as exc:
        raise TransactionTemplateNameTaken(changes.get("name", template.name)) from exc

    await session.refresh(template, ["payment_method"])
    return template


async def delete_template(session: AsyncSession, template_id: int) -> None:
    """Delete a template. Transactions created from it are unaffected."""
    template = await get_template(session, template_id)
    await session.delete(template)
    await session.flush()
