from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transactions.service import list_transactions

PAGE = "/transactions"


def _form(payment_method: PaymentMethod, **overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "txn_date": "2026-09-03",
        "merchant": "Star Market",
        "category": "Groceries",
        "subcategory": "",
        "amount": "43.18",
        "payment_method_id": str(payment_method.id),
        "notes": "",
    }
    return defaults | overrides


async def test_list_page_renders_empty(client: AsyncClient) -> None:
    response = await client.get(PAGE)
    assert response.status_code == 200
    assert "Nothing logged" in response.text


async def test_new_form_defaults_to_today(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.get(f"{PAGE}/new")
    assert response.status_code == 200
    today = date.today().isoformat()  # noqa: DTZ011  matches the route, local not UTC
    assert f'value="{today}"' in response.text


async def test_create_converts_dollars_to_cents(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """The form collects dollars, storage is integer cents"""
    response = await client.post(PAGE, data=_form(payment_method))
    assert response.status_code == 303

    rows = await list_transactions(session)
    assert [r.amount_cents for r in rows] == [4318]


async def test_create_returns_to_blank_form(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    """Entering one transaction usually means entering several"""
    response = await client.post(PAGE, data=_form(payment_method))
    assert response.headers["location"] == f"{PAGE}/new"


async def test_blank_subcategory_becomes_null(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    assert (await list_transactions(session))[0].subcategory is None


async def test_invalid_pair_rerenders_form(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    """A domain error keeps the user on the form instead of showing an error page"""
    response = await client.post(
        PAGE, data=_form(payment_method, category="Housing", subcategory="Gym")
    )
    assert response.status_code == 422
    assert 'class="error"' in response.text
    assert "not a valid combination" in response.text


async def test_bad_amount_rerenders_with_input_preserved(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.post(
        PAGE, data=_form(payment_method, amount="abc", merchant="Kept Merchant")
    )
    assert response.status_code == 422
    assert 'value="Kept Merchant"' in response.text


async def test_merchant_datalist_uses_history(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method, merchant="HK Market"))
    response = await client.get(f"{PAGE}/new")
    assert '<option value="HK Market">' in response.text


async def test_payment_method_defaults_to_last_used(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    response = await client.get(f"{PAGE}/new")
    assert f'value="{payment_method.id}" selected' in response.text


async def test_month_filter_on_list_page(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method, txn_date="2026-09-15"))
    await client.post(PAGE, data=_form(payment_method, txn_date="2026-08-15"))

    september = await client.get(PAGE, params={"month": "2026-09"})
    assert "1 transactions" in september.text
    assert "$43.18" in september.text


async def test_edit_prefills_dollars(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    transaction_id = (await list_transactions(session))[0].id

    response = await client.get(f"{PAGE}/{transaction_id}/edit")
    assert 'value="43.18"' in response.text


async def test_delete(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    transaction_id = (await list_transactions(session))[0].id

    response = await client.post(f"{PAGE}/{transaction_id}/delete")
    assert response.status_code == 303
    assert await list_transactions(session) == []
