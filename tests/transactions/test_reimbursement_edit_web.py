"""Editing a reimbursement through the web UI.

The detail page only offers an inline mark-received, so a wrong amount, source or note had no way
to be corrected short of deleting the row and retyping it.
"""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
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
    get_reimbursement,
)


async def _seed(session: AsyncSession, payment_method: PaymentMethod) -> int:
    txn = await create_transaction(
        session,
        TransactionCreate(
            txn_date=date(2026, 9, 3),
            merchant="Star Market",
            category="Groceries",
            amount_cents=8000,
            payment_method_id=payment_method.id,
        ),
    )
    item = await create_reimbursement(
        session,
        txn.id,
        ReimbursementCreate(
            source=ReimbursementSource.OTHER,
            amount_cents=2500,
            notes="split with Elman",
        ),
    )
    await session.flush()
    return item.id


async def test_edit_page_prefills(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    item_id = await _seed(session, payment_method)

    page = await client.get(f"/reimbursements/{item_id}/edit")
    assert page.status_code == 200
    assert 'value="25.00"' in page.text
    assert "split with Elman" in page.text
    assert 'value="Other" selected' in page.text.replace("\n", " ")


async def test_edit_shows_the_parent_transaction(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Without it you cannot tell which transaction you are editing against."""
    item_id = await _seed(session, payment_method)

    page = await client.get(f"/reimbursements/{item_id}/edit")
    assert "Star Market" in page.text


async def test_saving_updates_every_field(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    item_id = await _seed(session, payment_method)

    response = await client.post(
        f"/reimbursements/{item_id}/edit",
        data={
            "source": "Friend",
            "amount": "31.50",
            "status": "received",
            "received_date": "2026-10-01",
            "notes": "settled on Venmo",
        },
    )
    assert response.status_code == 303

    session.expire_all()
    item = await get_reimbursement(session, item_id)
    assert item.source is ReimbursementSource.FRIEND
    assert item.amount_cents == 3150
    assert item.status is ReimbursementStatus.RECEIVED
    assert item.received_date == date(2026, 10, 1)
    assert item.notes == "settled on Venmo"


async def test_saving_returns_to_the_transaction(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    item_id = await _seed(session, payment_method)
    item = await get_reimbursement(session, item_id)

    response = await client.post(
        f"/reimbursements/{item_id}/edit",
        data={"source": "Other", "amount": "25.00", "status": "expected", "notes": ""},
    )
    assert response.headers["location"] == f"/transactions/{item.transaction_id}"


async def test_invalid_amount_rerenders_with_input_kept(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Re-rendering this form rather than the detail page is why it has its own POST."""
    item_id = await _seed(session, payment_method)

    response = await client.post(
        f"/reimbursements/{item_id}/edit",
        data={
            "source": "Friend",
            "amount": "0",
            "status": "expected",
            "notes": "keep me",
        },
    )
    assert response.status_code == 422
    assert 'class="error"' in response.text
    assert "keep me" in response.text


async def test_received_without_a_date_is_rejected(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    item_id = await _seed(session, payment_method)

    response = await client.post(
        f"/reimbursements/{item_id}/edit",
        data={
            "source": "Other",
            "amount": "25.00",
            "status": "received",
            "received_date": "",
            "notes": "",
        },
    )
    assert response.status_code >= 400

    session.expire_all()
    item = await get_reimbursement(session, item_id)
    assert item.status is ReimbursementStatus.EXPECTED


async def test_detail_page_links_to_edit_and_shows_notes(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    item_id = await _seed(session, payment_method)
    item = await get_reimbursement(session, item_id)

    page = await client.get(f"/transactions/{item.transaction_id}")
    assert f'href="/reimbursements/{item_id}/edit"' in page.text
    # notes were stored but never rendered anywhere before
    assert "split with Elman" in page.text
