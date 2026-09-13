import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.categories import InvalidCategoryPair
from jyyfinhub_spendtracker.payment_methods.exceptions import PaymentMethodNotFound
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transaction_templates import service
from jyyfinhub_spendtracker.transaction_templates.exceptions import (
    TransactionTemplateNameTaken,
    TransactionTemplateNotFound,
)
from jyyfinhub_spendtracker.transaction_templates.schemas import (
    TransactionTemplateCreate,
    TransactionTemplateUpdate,
)


def _payload(
    payment_method: PaymentMethod, **overrides: object
) -> TransactionTemplateCreate:
    defaults: dict[str, object] = {
        "name": "Amazon Prime",
        "merchant": "Amazon",
        "category": "Subscriptions",
        "subcategory": "Entertainment",
        "amount_cents": 1499,
        "payment_method_id": payment_method.id,
        "is_subscription": True,
    }
    return TransactionTemplateCreate(**(defaults | overrides))  # type: ignore[arg-type]


async def test_get_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(TransactionTemplateNotFound):
        await service.get_template(session, 999)


async def test_create_fixed_amount(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    template = await service.create_template(session, _payload(payment_method))
    assert template.amount_cents == 1499
    assert template.is_active is True
    # lazy="raise" would blow up here if the service forgot to load it
    assert template.payment_method.name == payment_method.name


async def test_null_amount_means_varies(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Groceries and electricity change every time, so the form leaves the amount blank"""
    template = await service.create_template(
        session, _payload(payment_method, name="Star Market", amount_cents=None)
    )
    assert template.amount_cents is None


async def test_zero_amount_rejected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    with pytest.raises(ValueError):
        _payload(payment_method, amount_cents=0)


async def test_duplicate_name_raises(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await service.create_template(session, _payload(payment_method))
    with pytest.raises(TransactionTemplateNameTaken):
        await service.create_template(session, _payload(payment_method))


async def test_invalid_category_pair_rejected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A template must not be able to produce an invalid transaction"""
    with pytest.raises(InvalidCategoryPair):
        await service.create_template(
            session, _payload(payment_method, category="Housing", subcategory="Gym")
        )


async def test_unknown_payment_method_rejected(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    with pytest.raises(PaymentMethodNotFound):
        await service.create_template(
            session, _payload(payment_method, payment_method_id=9999)
        )


async def test_list_filters_inactive(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await service.create_template(session, _payload(payment_method, name="Active One"))
    await service.create_template(
        session, _payload(payment_method, name="Retired One", is_active=False)
    )

    active = await service.list_templates(session, is_active=True)
    assert [t.name for t in active] == ["Active One"]
    assert len(await service.list_templates(session)) == 2


async def test_update_validates_merged_state(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    created = await service.create_template(
        session, _payload(payment_method, category="Housing", subcategory="Rent")
    )

    with pytest.raises(InvalidCategoryPair):
        await service.update_template(
            session, created.id, TransactionTemplateUpdate(subcategory="Gym")
        )

    updated = await service.update_template(
        session, created.id, TransactionTemplateUpdate(is_active=False)
    )
    assert updated.is_active is False
    assert updated.subcategory == "Rent"


async def test_delete(session: AsyncSession, payment_method: PaymentMethod) -> None:
    created = await service.create_template(session, _payload(payment_method))
    await service.delete_template(session, created.id)

    with pytest.raises(TransactionTemplateNotFound):
        await service.get_template(session, created.id)
