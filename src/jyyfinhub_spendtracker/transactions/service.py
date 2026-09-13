"""Transaction and reimbursement business logic, shared by the API, web routes, and CLI.

Services flush but never commit. The caller owns the transaction boundary.
"""

import logging
from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jyyfinhub_spendtracker.categories import InvalidCategoryPair, is_valid_pair
from jyyfinhub_spendtracker.payment_methods.service import get_payment_method
from jyyfinhub_spendtracker.transactions.exceptions import (
    ReimbursementNeedsReceivedDate,
    ReimbursementNotFound,
    TransactionNotFound,
)
from jyyfinhub_spendtracker.transactions.models import (
    Reimbursement,
    ReimbursementStatus,
    Transaction,
)
from jyyfinhub_spendtracker.transactions.schemas import (
    ReimbursementCreate,
    ReimbursementUpdate,
    TransactionCreate,
    TransactionUpdate,
)

logger = logging.getLogger(__name__)


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
        .options(
            selectinload(Transaction.payment_method),
            selectinload(Transaction.reimbursements),
        )
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
        .options(
            selectinload(Transaction.payment_method),
            # one extra query for the whole page, not one per row
            selectinload(Transaction.reimbursements),
        )
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

    # the relationships are lazy="raise", so load them before anyone reads net_cents
    await session.refresh(transaction, ["payment_method", "reimbursements"])
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
    await session.refresh(transaction, ["payment_method", "reimbursements"])
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


def _check_received_has_date(
    status: ReimbursementStatus, received_date: date | None
) -> None:
    """Enforced here as well as by a DB CHECK, so the caller gets a usable message."""
    if status is ReimbursementStatus.RECEIVED and received_date is None:
        raise ReimbursementNeedsReceivedDate


def _warn_if_implausible(transaction: Transaction, amount_cents: int) -> None:
    """Soft guard against a fat-fingered amount. Never blocks: over-reimbursement is real."""
    if amount_cents > transaction.amount_cents * 2:
        logger.warning(
            "reimbursement of %s cents is more than double transaction %s (%s cents)",
            amount_cents,
            transaction.id,
            transaction.amount_cents,
        )


async def get_reimbursement(
    session: AsyncSession, reimbursement_id: int
) -> Reimbursement:
    """Get a single reimbursement by ID."""
    reimbursement = await session.get(Reimbursement, reimbursement_id)
    if reimbursement is None:
        raise ReimbursementNotFound(reimbursement_id)
    return reimbursement


async def list_reimbursements(
    session: AsyncSession, transaction_id: int
) -> Sequence[Reimbursement]:
    """Every reimbursement against a transaction, oldest first."""
    await get_transaction(session, transaction_id)
    stmt = (
        select(Reimbursement)
        .where(Reimbursement.transaction_id == transaction_id)
        .order_by(Reimbursement.id)
    )
    return (await session.scalars(stmt)).all()


async def create_reimbursement(
    session: AsyncSession, transaction_id: int, data: ReimbursementCreate
) -> Reimbursement:
    """Record money coming back against a transaction."""
    transaction = await get_transaction(session, transaction_id)
    _check_received_has_date(data.status, data.received_date)
    _warn_if_implausible(transaction, data.amount_cents)

    # append rather than setting transaction_id directly, so the parent's already-loaded
    # collection stays correct within this session and net_cents does not read stale
    reimbursement = Reimbursement(**data.model_dump())
    transaction.reimbursements.append(reimbursement)
    await session.flush()
    return reimbursement


async def update_reimbursement(
    session: AsyncSession, reimbursement_id: int, data: ReimbursementUpdate
) -> Reimbursement:
    """Update a reimbursement, validating the state it ends up in."""
    reimbursement = await get_reimbursement(session, reimbursement_id)
    changes = data.model_dump(exclude_unset=True)

    # marking received without also sending a date must fail, so check the merged result
    _check_received_has_date(
        changes.get("status", reimbursement.status),
        changes.get("received_date", reimbursement.received_date),
    )

    for field, value in changes.items():
        setattr(reimbursement, field, value)

    await session.flush()
    return reimbursement


async def delete_reimbursement(session: AsyncSession, reimbursement_id: int) -> None:
    """Delete a reimbursement. The transaction is unaffected."""
    reimbursement = await get_reimbursement(session, reimbursement_id)
    await session.delete(reimbursement)
    await session.flush()


async def received_cents_for(session: AsyncSession, transaction_id: int) -> int:
    """Total actually received against a transaction. Only RECEIVED counts."""
    stmt = select(func.coalesce(func.sum(Reimbursement.amount_cents), 0)).where(
        Reimbursement.transaction_id == transaction_id,
        Reimbursement.status == ReimbursementStatus.RECEIVED,
    )
    return await session.scalar(stmt) or 0
