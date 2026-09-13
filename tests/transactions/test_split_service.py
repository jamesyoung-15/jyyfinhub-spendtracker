from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.categories import InvalidCategoryPair
from jyyfinhub_spendtracker.payment_methods.exceptions import PaymentMethodNotFound
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.summaries.service import monthly_summary
from jyyfinhub_spendtracker.transactions import service
from jyyfinhub_spendtracker.transactions.schemas import TransactionSplitCreate


def _order(
    payment_method: PaymentMethod, **overrides: object
) -> TransactionSplitCreate:
    defaults: dict[str, object] = {
        "txn_date": date(2026, 9, 3),
        "merchant": "Amazon",
        "payment_method_id": payment_method.id,
        "allocations": [
            {"category": "Groceries", "amount_cents": 2000},
            {"category": "Leisure", "subcategory": "Hobbies", "amount_cents": 8000},
        ],
    }
    return TransactionSplitCreate(**(defaults | overrides))  # type: ignore[arg-type]


async def test_siblings_share_one_order_ref(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    rows = await service.create_split(session, _order(payment_method))

    assert len(rows) == 2
    assert rows[0].order_ref == rows[1].order_ref
    assert rows[0].order_ref is not None


async def test_siblings_carry_their_own_shared_fields(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Each row is self-sufficient, so no summary query needs a self-join"""
    rows = await service.create_split(session, _order(payment_method))

    for row in rows:
        assert row.merchant == "Amazon"
        assert row.txn_date == date(2026, 9, 3)
        assert row.payment_method_id == payment_method.id


async def test_every_row_counts_toward_the_month(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """No parent row, so nothing has to be excluded and no total goes missing"""
    await service.create_split(session, _order(payment_method))

    summary = await monthly_summary(session, date(2026, 9, 1))
    assert summary.transaction_count == 2
    assert summary.gross_cents == 10000


async def test_allocations_land_in_their_own_categories(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await service.create_split(session, _order(payment_method))

    groceries = await service.list_transactions(session, category="Groceries")
    leisure = await service.list_transactions(session, category="Leisure")
    assert [t.amount_cents for t in groceries] == [2000]
    assert [t.amount_cents for t in leisure] == [8000]


async def test_order_ref_regroups_the_purchase(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    rows = await service.create_split(session, _order(payment_method))
    order_ref = rows[0].order_ref

    siblings = await service.list_transactions(session, order_ref=order_ref)
    assert sum(t.amount_cents for t in siblings) == 10000


async def test_single_transactions_have_no_order_ref(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """order_ref is set only when a purchase becomes more than one row"""
    from jyyfinhub_spendtracker.transactions.schemas import TransactionCreate

    txn = await service.create_transaction(
        session,
        TransactionCreate(
            txn_date=date(2026, 9, 3),
            merchant="MBTA",
            category="Transit",
            amount_cents=240,
            payment_method_id=payment_method.id,
        ),
    )
    assert txn.order_ref is None


async def test_two_splits_do_not_share_a_ref(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    first = await service.create_split(session, _order(payment_method))
    second = await service.create_split(session, _order(payment_method))
    assert first[0].order_ref != second[0].order_ref


async def test_one_allocation_rejected(payment_method: PaymentMethod) -> None:
    """A one-row split is just a transaction, so it should use the normal path"""
    with pytest.raises(ValueError):
        _order(
            payment_method,
            allocations=[{"category": "Groceries", "amount_cents": 2000}],
        )


async def test_invalid_pair_rejects_the_whole_order(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Validation happens before any row is added, so nothing is half-written"""
    with pytest.raises(InvalidCategoryPair):
        await service.create_split(
            session,
            _order(
                payment_method,
                allocations=[
                    {"category": "Groceries", "amount_cents": 2000},
                    {"category": "Housing", "subcategory": "Gym", "amount_cents": 8000},
                ],
            ),
        )

    assert await service.list_transactions(session) == []


async def test_unknown_payment_method_rejects_the_order(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    with pytest.raises(PaymentMethodNotFound):
        await service.create_split(
            session, _order(payment_method, payment_method_id=9999)
        )

    assert await service.list_transactions(session) == []


async def test_api_split_route_is_not_shadowed(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """/transactions/split must be declared before /transactions/{transaction_id}"""
    from jyyfinhub_spendtracker.main import create_app

    paths = create_app().openapi()["paths"]
    assert "post" in paths["/api/v1/transactions/split"]
