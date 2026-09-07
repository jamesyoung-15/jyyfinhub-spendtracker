from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods import service
from jyyfinhub_spendtracker.payment_methods.exceptions import (
    PaymentMethodNameTaken,
    PaymentMethodNotFound,
)
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethodKind
from jyyfinhub_spendtracker.payment_methods.schemas import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
)


async def test_get_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(PaymentMethodNotFound):
        await service.get_payment_method(session, 999)


async def test_create_populates_server_defaults(session: AsyncSession) -> None:
    """INSERT ... RETURNING fills these in, so no refresh() is needed after flush"""
    pm = await service.create_payment_method(
        session, PaymentMethodCreate(name="Card A", kind=PaymentMethodKind.CREDIT)
    )
    assert pm.id is not None
    assert pm.created_at is not None
    assert pm.is_active is True


async def test_duplicate_name_raises(session: AsyncSession) -> None:
    await service.create_payment_method(session, PaymentMethodCreate(name="Dup"))
    with pytest.raises(PaymentMethodNameTaken):
        await service.create_payment_method(session, PaymentMethodCreate(name="Dup"))


async def test_expires_filter_excludes_nulls(session: AsyncSession) -> None:
    """NULL fails every comparison, so a date filter drops cards that never expire"""
    await service.create_payment_method(
        session, PaymentMethodCreate(name="Expiring", expires_on=date(2028, 3, 1))
    )
    await service.create_payment_method(session, PaymentMethodCreate(name="Forever"))

    hits = await service.list_payment_methods(session, expires_from=date(2028, 1, 1))
    assert [p.name for p in hits] == ["Expiring"]

    hits = await service.list_payment_methods(
        session, expires_from=date(2028, 1, 1), include_never_expires=True
    )
    assert [p.name for p in hits] == ["Expiring", "Forever"]


async def test_update_leaves_unset_fields_alone(session: AsyncSession) -> None:
    """exclude_unset is what makes an omitted field differ from an explicit null"""
    pm = await service.create_payment_method(
        session, PaymentMethodCreate(name="Keep", notes="original")
    )

    updated = await service.update_payment_method(
        session, pm.id, PaymentMethodUpdate(is_active=False)
    )
    assert updated.notes == "original"
    assert updated.is_active is False

    cleared = await service.update_payment_method(
        session, pm.id, PaymentMethodUpdate(notes=None)
    )
    assert cleared.notes is None
