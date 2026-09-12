from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.exceptions import PaymentMethodNotFound
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transactions import service
from jyyfinhub_spendtracker.transactions.exceptions import (
    InvalidCategoryPair,
    TransactionNotFound,
)
from jyyfinhub_spendtracker.transactions.schemas import (
    TransactionCreate,
    TransactionUpdate,
)


def _payload(payment_method: PaymentMethod, **overrides: object) -> TransactionCreate:
    defaults: dict[str, object] = {
        "txn_date": date(2026, 9, 3),
        "merchant": "Star Market",
        "category": "Groceries",
        "subcategory": None,
        "amount_cents": 4318,
        "payment_method_id": payment_method.id,
    }
    return TransactionCreate(**(defaults | overrides))  # type: ignore[arg-type]


async def test_get_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(TransactionNotFound):
        await service.get_transaction(session, 999)


async def test_create_and_read_back(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    created = await service.create_transaction(session, _payload(payment_method))
    assert created.id is not None
    assert created.order_ref is None

    fetched = await service.get_transaction(session, created.id)
    assert fetched.merchant == "Star Market"
    # lazy="raise" would blow up here if the service forgot to load it
    assert fetched.payment_method.name == payment_method.name


async def test_invalid_category_pair_rejected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Gym is real, but it belongs to Health & Fitness, so the pair is invalid"""
    with pytest.raises(InvalidCategoryPair):
        await service.create_transaction(
            session, _payload(payment_method, category="Housing", subcategory="Gym")
        )


async def test_flat_category_rejects_subcategory(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    with pytest.raises(InvalidCategoryPair):
        await service.create_transaction(
            session, _payload(payment_method, category="Groceries", subcategory="Food")
        )


async def test_unknown_payment_method_rejected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Asking the owning service gives a real error instead of an IntegrityError"""
    with pytest.raises(PaymentMethodNotFound):
        await service.create_transaction(
            session, _payload(payment_method, payment_method_id=9999)
        )


async def test_month_filter_is_a_half_open_range(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    for day in (
        date(2026, 8, 31),
        date(2026, 9, 1),
        date(2026, 9, 30),
        date(2026, 10, 1),
    ):
        await service.create_transaction(
            session, _payload(payment_method, txn_date=day, merchant=day.isoformat())
        )

    hits = await service.list_transactions(session, month=date(2026, 9, 15))
    assert sorted(t.merchant for t in hits) == ["2026-09-01", "2026-09-30"]


async def test_december_month_bounds_roll_over() -> None:
    """The year has to increment, which is the case a naive month + 1 gets wrong"""
    assert service.month_bounds(date(2026, 12, 9)) == (
        date(2026, 12, 1),
        date(2027, 1, 1),
    )


async def test_update_validates_merged_state(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Sending only subcategory must be checked against the stored category"""
    created = await service.create_transaction(
        session, _payload(payment_method, category="Housing", subcategory="Rent")
    )

    with pytest.raises(InvalidCategoryPair):
        await service.update_transaction(
            session, created.id, TransactionUpdate(subcategory="Gym")
        )

    updated = await service.update_transaction(
        session, created.id, TransactionUpdate(subcategory="Electricity")
    )
    assert updated.category == "Housing"
    assert updated.subcategory == "Electricity"


async def test_delete(session: AsyncSession, payment_method: PaymentMethod) -> None:
    created = await service.create_transaction(session, _payload(payment_method))
    await service.delete_transaction(session, created.id)

    with pytest.raises(TransactionNotFound):
        await service.get_transaction(session, created.id)
