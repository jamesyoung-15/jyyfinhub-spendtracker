from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transactions.service import (
    list_reimbursements,
    list_transactions,
)

PAGE = "/transactions"


async def _transaction_id(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> int:
    await client.post(
        PAGE,
        data={
            "txn_date": "2026-09-03",
            "merchant": "Work Trip",
            "category": "Travel",
            "subcategory": "Transport",
            "amount": "400.00",
            "payment_method_id": str(payment_method.id),
            "notes": "",
        },
    )
    return (await list_transactions(session))[0].id


def _form(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "source": "Company",
        "amount": "400.00",
        "status": "expected",
        "received_date": "",
        "notes": "",
    }
    return defaults | overrides


async def test_detail_page_shows_totals(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn_id = await _transaction_id(client, session, payment_method)

    page = await client.get(f"{PAGE}/{txn_id}")
    assert page.status_code == 200
    assert "Work Trip" in page.text
    assert "None recorded" in page.text


async def test_list_links_to_detail(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn_id = await _transaction_id(client, session, payment_method)
    listing = await client.get(PAGE)
    assert f'href="/transactions/{txn_id}"' in listing.text


async def test_add_reimbursement(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn_id = await _transaction_id(client, session, payment_method)

    response = await client.post(f"{PAGE}/{txn_id}/reimbursements", data=_form())
    assert response.status_code == 303
    assert response.headers["location"] == f"{PAGE}/{txn_id}"

    claims = await list_reimbursements(session, txn_id)
    assert [(c.source.value, c.amount_cents) for c in claims] == [("Company", 40000)]


async def test_net_floors_at_zero(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """Over-reimbursement is stored, but net never goes negative"""
    txn_id = await _transaction_id(client, session, payment_method)
    await client.post(
        f"{PAGE}/{txn_id}/reimbursements",
        data=_form(amount="500.00", status="received", received_date="2026-10-01"),
    )

    page = await client.get(f"{PAGE}/{txn_id}")
    assert "$0.00" in page.text
    assert "not counted as income" in page.text


async def test_received_without_date_rerenders_detail(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn_id = await _transaction_id(client, session, payment_method)

    response = await client.post(
        f"{PAGE}/{txn_id}/reimbursements", data=_form(status="received")
    )
    assert response.status_code == 422
    assert "needs a received_date" in response.text


async def test_mark_received_inline(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """The common transition, done from the row without opening a form"""
    txn_id = await _transaction_id(client, session, payment_method)
    await client.post(f"{PAGE}/{txn_id}/reimbursements", data=_form())
    claim_id = (await list_reimbursements(session, txn_id))[0].id

    response = await client.post(
        f"/reimbursements/{claim_id}",
        data={"status": "received", "received_date": "2026-10-15"},
    )
    assert response.status_code == 303

    claim = (await list_reimbursements(session, txn_id))[0]
    assert claim.status.value == "received"
    assert claim.received_date is not None


async def test_delete_reimbursement(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    txn_id = await _transaction_id(client, session, payment_method)
    await client.post(f"{PAGE}/{txn_id}/reimbursements", data=_form())
    claim_id = (await list_reimbursements(session, txn_id))[0].id

    response = await client.post(f"/reimbursements/{claim_id}/delete")
    assert response.status_code == 303
    assert await list_reimbursements(session, txn_id) == []


async def test_missing_transaction_renders_html_404(client: AsyncClient) -> None:
    response = await client.get(f"{PAGE}/9999")
    assert response.status_code == 404
    assert "<html" in response.text
