from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod


async def test_commit_is_visible(session: AsyncSession) -> None:
    """Ensure commit works inside test"""
    session.add(PaymentMethod(name="Committed", kind="credit"))
    await session.commit()
    assert await session.scalar(select(func.count()).select_from(PaymentMethod)) == 1


async def test_commit_rolls_back(session: AsyncSession) -> None:
    """Ensure commit from other tests rolls back and doesn't leak"""
    assert await session.scalar(select(func.count()).select_from(PaymentMethod)) == 0
