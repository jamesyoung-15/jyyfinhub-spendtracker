"""Category breakdown. The clamp rules are the same as the month totals, per category."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

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
    category: str,
    amount_cents: int,
    *,
    subcategory: str | None = None,
    day: date = date(2026, 9, 3),
) -> int:
    txn = await create_transaction(
        session,
        TransactionCreate(
            txn_date=day,
            merchant="Star Market",
            category=category,
            subcategory=subcategory,
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


async def test_empty_month_returns_nothing(session: AsyncSession) -> None:
    assert await service.monthly_categories(session, SEPTEMBER) == []


async def test_totals_per_category(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, "Groceries", 5000)
    await _spend(session, payment_method, "Groceries", 2500)
    await _spend(session, payment_method, "Transit", 240)

    rows = await service.monthly_categories(session, SEPTEMBER)
    assert [(r.category, r.gross_cents, r.transaction_count) for r in rows] == [
        ("Groceries", 7500, 2),
        ("Transit", 240, 1),
    ]


async def test_sorted_by_net_descending(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Net, not gross, so a fully reimbursed category sinks to the bottom."""
    big = await _spend(session, payment_method, "Groceries", 50000)
    await _received(session, big, 50000)
    await _spend(session, payment_method, "Transit", 1000)

    rows = await service.monthly_categories(session, SEPTEMBER)
    assert [r.category for r in rows] == ["Transit", "Groceries"]
    assert rows[1].net_cents == 0


async def test_clamp_is_per_transaction_within_a_category(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """An over-reimbursed row must not subsidise its own category."""
    over = await _spend(session, payment_method, "Groceries", 10000)
    await _received(session, over, 12000)
    await _spend(session, payment_method, "Groceries", 50000)

    rows = await service.monthly_categories(session, SEPTEMBER)
    assert rows[0].gross_cents == 60000
    assert rows[0].received_cents == 12000
    assert rows[0].net_cents == 50000


async def test_subcategories_roll_up_to_their_category(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, "Leisure", 8000, subcategory="Hobbies")
    await _spend(session, payment_method, "Leisure", 3000, subcategory="Gaming")
    await _spend(session, payment_method, "Leisure", 1000)

    rows = await service.monthly_categories(session, SEPTEMBER)
    assert len(rows) == 1
    leisure = rows[0]
    assert leisure.gross_cents == 12000
    assert leisure.transaction_count == 3
    assert sum(sub.gross_cents for sub in leisure.subcategories) == leisure.gross_cents


async def test_subcategories_sorted_by_net_descending(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, "Leisure", 3000, subcategory="Gaming")
    await _spend(session, payment_method, "Leisure", 8000, subcategory="Hobbies")

    rows = await service.monthly_categories(session, SEPTEMBER)
    assert [sub.subcategory for sub in rows[0].subcategories] == [
        "Hobbies",
        "Gaming",
    ]


async def test_blank_subcategory_stays_none(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A flat category has one child with no name, which the page renders as no child at all."""
    await _spend(session, payment_method, "Transit", 240)

    rows = await service.monthly_categories(session, SEPTEMBER)
    assert [sub.subcategory for sub in rows[0].subcategories] == [None]


async def test_month_boundaries(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, "Groceries", 100, day=date(2026, 8, 31))
    await _spend(session, payment_method, "Groceries", 200, day=date(2026, 9, 1))
    await _spend(session, payment_method, "Groceries", 400, day=date(2026, 9, 30))
    await _spend(session, payment_method, "Groceries", 800, day=date(2026, 10, 1))

    rows = await service.monthly_categories(session, SEPTEMBER)
    assert rows[0].gross_cents == 600


async def test_yearly_spans_the_whole_year(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await _spend(session, payment_method, "Groceries", 100, day=date(2026, 3, 4))
    await _spend(session, payment_method, "Groceries", 200, day=date(2026, 11, 4))
    await _spend(session, payment_method, "Groceries", 400, day=date(2027, 1, 1))

    rows = await service.yearly_categories(session, 2026)
    assert rows[0].gross_cents == 300


async def test_breakdown_totals_match_the_month_summary(
    session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """The two queries must never disagree, since both appear on the same page."""
    reimbursed = await _spend(session, payment_method, "Groceries", 40000)
    await _received(session, reimbursed, 15000)
    await _spend(session, payment_method, "Leisure", 8000, subcategory="Hobbies")
    await _spend(session, payment_method, "Transit", 240)

    rows = await service.monthly_categories(session, SEPTEMBER)
    summary = await service.monthly_summary(session, SEPTEMBER)

    assert sum(r.gross_cents for r in rows) == summary.gross_cents
    assert sum(r.received_cents for r in rows) == summary.received_cents
    assert sum(r.net_cents for r in rows) == summary.net_cents
    assert sum(r.transaction_count for r in rows) == summary.transaction_count
