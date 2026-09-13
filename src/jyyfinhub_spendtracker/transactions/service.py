"""Transaction business logic, shared by the API, web routes, and CLI.

Services flush but never commit. The caller owns the transaction boundary.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jyyfinhub_spendtracker.categories import InvalidCategoryPair, is_valid_pair
from jyyfinhub_spendtracker.payment_methods.service import get_payment_method
from jyyfinhub_spendtracker.transactions.exceptions import TransactionNotFound
from jyyfinhub_spendtracker.transactions.models import Transaction
from jyyfinhub_spendtracker.transactions.schemas import (
    TransactionCreate,
    TransactionUpdate,
)


def month_bounds(day: date) -> tuple[date, date]:
    """Half-open range covering the month `day` falls in.

    A range keeps the txn_date index usable, unlike wrapping the column in date_trunc.
    """
    start = day.replace(day=1)
    # rolling over December without any date arithmetic library
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, end


def year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year + 1, 1, 1)


async def _validate(
    session: AsyncSession,
    category: str,
    subcategory: str | None,
    payment_method_id: int,
) -> None:
    """Rules the database cannot express on its own."""
    # a pair constraint spans two columns' allowed values, so no CHECK can state it
    if not is_valid_pair(category, subcategory):
        raise InvalidCategoryPair(category, subcategory)

    # asking the owning service gives a real error message instead of an IntegrityError
    await get_payment_method(session, payment_method_id)


async def get_transaction(session: AsyncSession, transaction_id: int) -> Transaction:
    """Get a single transaction by ID, with its payment method loaded."""
    stmt = (
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .options(selectinload(Transaction.payment_method))
    )
    transaction = await session.scalar(stmt)
    if transaction is None:
        raise TransactionNotFound(transaction_id)
    return transaction


async def list_transactions(
    session: AsyncSession,
    *,
    month: date | None = None,
    year: int | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    order_ref: str | None = None,
) -> Sequence[Transaction]:
    """List transactions, newest first, with payment methods eager-loaded.

    `month` may be any day in the wanted month.
    """
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.payment_method))
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    )

    if month is not None:
        start, end = month_bounds(month)
        stmt = stmt.where(Transaction.txn_date >= start, Transaction.txn_date < end)
    elif year is not None:
        start, end = year_bounds(year)
        stmt = stmt.where(Transaction.txn_date >= start, Transaction.txn_date < end)

    if category is not None:
        stmt = stmt.where(Transaction.category == category)
    if subcategory is not None:
        stmt = stmt.where(Transaction.subcategory == subcategory)
    if order_ref is not None:
        stmt = stmt.where(Transaction.order_ref == order_ref)

    return (await session.scalars(stmt)).all()


async def create_transaction(
    session: AsyncSession, data: TransactionCreate
) -> Transaction:
    """Create a transaction."""
    await _validate(session, data.category, data.subcategory, data.payment_method_id)

    transaction = Transaction(**data.model_dump())
    session.add(transaction)
    await session.flush()

    # the relationship is lazy="raise", so load it before anyone reads it
    await session.refresh(transaction, ["payment_method"])
    return transaction


async def update_transaction(
    session: AsyncSession, transaction_id: int, data: TransactionUpdate
) -> Transaction:
    """Update a transaction, validating the state it ends up in."""
    transaction = await get_transaction(session, transaction_id)
    changes = data.model_dump(exclude_unset=True)

    # a partial update may send only subcategory, so validate the merged result rather than
    # the payload, or "Housing" + a new "Gym" would slip through
    await _validate(
        session,
        changes.get("category", transaction.category),
        changes.get("subcategory", transaction.subcategory),
        changes.get("payment_method_id", transaction.payment_method_id),
    )

    for field, value in changes.items():
        setattr(transaction, field, value)

    await session.flush()
    await session.refresh(transaction, ["payment_method"])
    return transaction


async def delete_transaction(session: AsyncSession, transaction_id: int) -> None:
    """Delete a transaction. Reimbursements cascade with it."""
    transaction = await get_transaction(session, transaction_id)
    await session.delete(transaction)
    await session.flush()


async def recent_merchants(session: AsyncSession, limit: int = 50) -> Sequence[str]:
    """Distinct merchants, most recently used first, for the entry form datalist."""
    stmt = (
        select(Transaction.merchant)
        .group_by(Transaction.merchant)
        .order_by(func.max(Transaction.txn_date).desc())
        .limit(limit)
    )
    return (await session.scalars(stmt)).all()


async def last_used_payment_method_id(session: AsyncSession) -> int | None:
    """Default for the entry form, since the same card is usually used repeatedly."""
    stmt = (
        select(Transaction.payment_method_id).order_by(Transaction.id.desc()).limit(1)
    )
    return await session.scalar(stmt)
