from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.goals.schemas import MonthlyBudgetGoalUpsert
from jyyfinhub_spendtracker.goals.service import upsert_goal
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.summaries import service
from jyyfinhub_spendtracker.transactions.models import (
    ReimbursementSource,
    ReimbursementStatus,
)
from jyyfinhub_spendtracker.transactions.schemas import (
    ReimbursementCreate,
    TransactionCreate,
)
from jyyfinhub_spendtracker.transactions.service import (
    create_reimbursement,
    create_transaction,
)

SEPTEMBER = date(2026, 9, 1)


async def _spend(
    session: AsyncSession,
    payment_method: PaymentMethod,
    amount_cents: int,
    *,
    day: date = date(2026, 9, 3),
) -> int:
    txn = await create_transaction(
        session,
        TransactionCreate(
            txn_date=day,
            merchant="Star Market",
            category="Groceries",
            amount_cents=amount_cents,
            payment_method_id=payment_method.id,
        ),
    )
    return txn.id


async def _received(
    session: AsyncSession, transaction_id: int, amount_cents: int
) -> None:
    await create_reimbursement(
        session,
        transaction_id,
        ReimbursementCreate(
            source=ReimbursementSource.COMPANY,
            amount_cents=amount_cents,
            status=ReimbursementStatus.RECEIVED,
            received_date=date(2026, 10, 15),
        ),
    )


async def test_empty_month_is_zero_not_null(session: AsyncSession) -> None:
    """SUM over no rows returns NULL, so every aggregate is coalesced"""
    summary = await service.monthly_summary(session, SEPTEMBER)

    assert summary.transaction_count == 0
    assert (summary.gross_cents, summary.received_cents, summary.net_cents) == (0, 0, 0)


async def test_no_goal_gives_no_variance(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A month with no goal is normal, and a zero variance would be misleading"""
    await _spend(session, payment_method, 5000)
    summary = await service.monthly_summary(session, SEPTEMBER)

    assert summary.goal_cents is None
    assert summary.variance_cents is None


async def test_variance_is_goal_minus_net(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, 150000)
    await upsert_goal(session, SEPTEMBER, MonthlyBudgetGoalUpsert(goal_cents=250000))

    summary = await service.monthly_summary(session, SEPTEMBER)
    assert summary.net_cents == 150000
    assert summary.variance_cents == 100000


async def test_reimbursement_reduces_net_not_gross(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn_id = await _spend(session, payment_method, 40000)
    await _received(session, txn_id, 15000)

    summary = await service.monthly_summary(session, SEPTEMBER)
    assert summary.gross_cents == 40000
    assert summary.received_cents == 15000
    assert summary.net_cents == 25000


async def test_clamp_is_per_transaction(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """An over-reimbursed dinner must not make other spending look cheaper"""
    over = await _spend(session, payment_method, 10000)
    await _received(session, over, 12000)
    await _spend(session, payment_method, 50000)

    summary = await service.monthly_summary(session, SEPTEMBER)
    assert summary.gross_cents == 60000
    assert summary.received_cents == 12000
    # 0 for the over-reimbursed one plus 50000, not 60000 - 12000
    assert summary.net_cents == 50000


async def test_only_received_counts(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn_id = await _spend(session, payment_method, 40000)
    await create_reimbursement(
        session,
        txn_id,
        ReimbursementCreate(source=ReimbursementSource.COMPANY, amount_cents=40000),
    )

    summary = await service.monthly_summary(session, SEPTEMBER)
    assert summary.received_cents == 0
    assert summary.net_cents == 40000


async def test_reimbursement_credits_the_transaction_month(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Spend in August, money back in October, and August is what changes"""
    august_id = await _spend(session, payment_method, 40000, day=date(2026, 8, 14))
    await _received(session, august_id, 40000)

    august = await service.monthly_summary(session, date(2026, 8, 1))
    october = await service.monthly_summary(session, date(2026, 10, 1))

    assert august.net_cents == 0
    assert october.gross_cents == 0
    assert october.received_cents == 0


async def test_month_boundaries(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, 100, day=date(2026, 8, 31))
    await _spend(session, payment_method, 200, day=date(2026, 9, 1))
    await _spend(session, payment_method, 400, day=date(2026, 9, 30))
    await _spend(session, payment_method, 800, day=date(2026, 10, 1))

    summary = await service.monthly_summary(session, SEPTEMBER)
    assert summary.gross_cents == 600


async def test_months_for_year_includes_goal_only_months(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A goal set for a month with no spending still belongs in the list"""
    await _spend(session, payment_method, 5000, day=date(2026, 3, 4))
    await upsert_goal(
        session, date(2026, 7, 1), MonthlyBudgetGoalUpsert(goal_cents=9999)
    )

    months = await service.monthly_summaries_for_year(session, 2026)
    assert [m.month_start for m in months] == [date(2026, 3, 1), date(2026, 7, 1)]
    assert months[1].gross_cents == 0
    assert months[1].goal_cents == 9999


async def test_yearly_goal_is_the_sum_of_months(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Monthly goals are the source of truth; the yearly figure is derived"""
    await _spend(session, payment_method, 100000, day=date(2026, 3, 4))
    await upsert_goal(
        session, date(2026, 3, 1), MonthlyBudgetGoalUpsert(goal_cents=200000)
    )
    await upsert_goal(
        session, date(2026, 4, 1), MonthlyBudgetGoalUpsert(goal_cents=150000)
    )

    yearly = await service.yearly_summary(session, 2026)
    assert yearly.goal_cents == 350000
    assert yearly.net_cents == 100000
    assert yearly.variance_cents == 250000


async def test_yearly_excludes_neighbouring_years(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, 100, day=date(2025, 12, 31))
    await _spend(session, payment_method, 200, day=date(2026, 6, 15))
    await _spend(session, payment_method, 400, day=date(2027, 1, 1))

    yearly = await service.yearly_summary(session, 2026)
    assert yearly.gross_cents == 200
