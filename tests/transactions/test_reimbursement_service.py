from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transactions import service
from jyyfinhub_spendtracker.transactions.exceptions import (
    ReimbursementNeedsReceivedDate,
    ReimbursementNotFound,
    TransactionNotFound,
)
from jyyfinhub_spendtracker.transactions.models import (
    Reimbursement,
    ReimbursementSource,
    ReimbursementStatus,
    Transaction,
)
from jyyfinhub_spendtracker.transactions.schemas import (
    ReimbursementCreate,
    ReimbursementUpdate,
    TransactionCreate,
)


async def _transaction(
    session: AsyncSession, payment_method: PaymentMethod, amount_cents: int = 40000
) -> Transaction:
    return await service.create_transaction(
        session,
        TransactionCreate(
            txn_date=date(2026, 9, 3),
            merchant="Work Trip",
            category="Travel",
            subcategory="Transport",
            amount_cents=amount_cents,
            payment_method_id=payment_method.id,
        ),
    )


def _claim(**overrides: object) -> ReimbursementCreate:
    defaults: dict[str, object] = {
        "source": ReimbursementSource.COMPANY,
        "amount_cents": 40000,
    }
    return ReimbursementCreate(**(defaults | overrides))  # type: ignore[arg-type]


async def test_get_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(ReimbursementNotFound):
        await service.get_reimbursement(session, 999)


async def test_list_for_missing_transaction_raises(session: AsyncSession) -> None:
    with pytest.raises(TransactionNotFound):
        await service.list_reimbursements(session, 999)


async def test_create_defaults_to_expected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn = await _transaction(session, payment_method)
    claim = await service.create_reimbursement(session, txn.id, _claim())

    assert claim.status is ReimbursementStatus.EXPECTED
    assert claim.received_date is None


async def test_received_without_date_rejected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Enforced in the service so the caller gets a message, and by a DB CHECK as backstop"""
    txn = await _transaction(session, payment_method)
    with pytest.raises(ReimbursementNeedsReceivedDate):
        await service.create_reimbursement(
            session, txn.id, _claim(status=ReimbursementStatus.RECEIVED)
        )


async def test_marking_received_without_date_rejected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A PATCH sending only status must be checked against the stored received_date"""
    txn = await _transaction(session, payment_method)
    claim = await service.create_reimbursement(session, txn.id, _claim())

    with pytest.raises(ReimbursementNeedsReceivedDate):
        await service.update_reimbursement(
            session, claim.id, ReimbursementUpdate(status=ReimbursementStatus.RECEIVED)
        )

    updated = await service.update_reimbursement(
        session,
        claim.id,
        ReimbursementUpdate(
            status=ReimbursementStatus.RECEIVED, received_date=date(2026, 10, 15)
        ),
    )
    assert updated.status is ReimbursementStatus.RECEIVED


async def test_over_reimbursement_is_recordable(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A colleague rounding up must be storable. Clamping is a reporting rule, not a constraint"""
    txn = await _transaction(session, payment_method, amount_cents=10000)
    claim = await service.create_reimbursement(
        session,
        txn.id,
        _claim(
            amount_cents=12000,
            status=ReimbursementStatus.RECEIVED,
            received_date=date(2026, 10, 1),
        ),
    )
    assert claim.amount_cents > txn.amount_cents


async def test_received_total_counts_only_received(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn = await _transaction(session, payment_method)
    await service.create_reimbursement(
        session,
        txn.id,
        _claim(
            amount_cents=10000,
            status=ReimbursementStatus.RECEIVED,
            received_date=date(2026, 10, 1),
        ),
    )
    await service.create_reimbursement(session, txn.id, _claim(amount_cents=5000))
    await service.create_reimbursement(
        session,
        txn.id,
        _claim(amount_cents=7000, status=ReimbursementStatus.CANCELLED),
    )

    assert await service.received_cents_for(session, txn.id) == 10000


async def test_no_reimbursements_totals_zero(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """coalesce keeps this an int rather than None, which the summary math relies on"""
    txn = await _transaction(session, payment_method)
    assert await service.received_cents_for(session, txn.id) == 0


async def test_deleting_transaction_cascades(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """ON DELETE CASCADE in the database, with passive_deletes so lazy="raise" is not tripped"""
    txn = await _transaction(session, payment_method)
    await service.create_reimbursement(session, txn.id, _claim())

    await service.delete_transaction(session, txn.id)

    remaining = await session.scalar(select(func.count()).select_from(Reimbursement))
    assert remaining == 0


async def test_delete_reimbursement_leaves_transaction(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn = await _transaction(session, payment_method)
    claim = await service.create_reimbursement(session, txn.id, _claim())

    await service.delete_reimbursement(session, claim.id)

    assert await service.list_reimbursements(session, txn.id) == []
    assert await service.get_transaction(session, txn.id) is not None


async def test_net_properties_need_no_extra_query(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """list_transactions eager-loads reimbursements, so net_cents works without N+1"""
    txn = await _transaction(session, payment_method, amount_cents=40000)
    await service.create_reimbursement(
        session,
        txn.id,
        _claim(
            amount_cents=15000,
            status=ReimbursementStatus.RECEIVED,
            received_date=date(2026, 10, 1),
        ),
    )

    listed = await service.list_transactions(session)
    assert [(t.received_cents, t.net_cents) for t in listed] == [(15000, 25000)]


async def test_net_floors_at_zero_on_the_model(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn = await _transaction(session, payment_method, amount_cents=10000)
    await service.create_reimbursement(
        session,
        txn.id,
        _claim(
            amount_cents=12000,
            status=ReimbursementStatus.RECEIVED,
            received_date=date(2026, 10, 1),
        ),
    )

    refreshed = await service.get_transaction(session, txn.id)
    assert refreshed.received_cents == 12000
    assert refreshed.net_cents == 0
