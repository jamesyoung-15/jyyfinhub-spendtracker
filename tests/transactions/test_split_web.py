from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transactions.service import list_transactions

PAGE = "/transactions/split"


def _form(payment_method: PaymentMethod, **overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "txn_date": "2026-09-03",
        "merchant": "Amazon",
        "payment_method_id": str(payment_method.id),
        "category_0": "Groceries",
        "subcategory_0": "",
        "amount_0": "20.00",
        "notes_0": "",
        "category_1": "Leisure",
        "subcategory_1": "Hobbies",
        "amount_1": "80.00",
        "notes_1": "model kit",
        "category_2": "",
        "subcategory_2": "",
        "amount_2": "",
        "notes_2": "",
    }
    return defaults | overrides


async def test_form_renders(client: AsyncClient, payment_method: PaymentMethod) -> None:
    response = await client.get(PAGE)
    assert response.status_code == 200
    assert "Allocations" in response.text


async def test_split_creates_sibling_rows(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    response = await client.post(PAGE, data=_form(payment_method))
    assert response.status_code == 303

    rows = await list_transactions(session)
    assert len(rows) == 2
    assert rows[0].order_ref == rows[1].order_ref
    assert sorted(t.amount_cents for t in rows) == [2000, 8000]


async def test_blank_rows_are_ignored(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """The form always offers five rows, so unused ones must not become errors"""
    await client.post(PAGE, data=_form(payment_method))
    assert len(await list_transactions(session)) == 2


async def test_returns_to_a_blank_split_form(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.post(PAGE, data=_form(payment_method))
    assert response.headers["location"] == PAGE


async def test_one_allocation_rerenders(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    response = await client.post(
        PAGE, data=_form(payment_method, category_1="", amount_1="")
    )
    assert response.status_code == 422
    assert 'class="error"' in response.text
    assert await list_transactions(session) == []


async def test_invalid_pair_rerenders_with_input_kept(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    response = await client.post(
        PAGE, data=_form(payment_method, category_1="Housing", subcategory_1="Gym")
    )
    assert response.status_code == 422
    assert "not a valid combination" in response.text
    assert 'value="20.00"' in response.text
    assert await list_transactions(session) == []


async def test_entry_form_links_to_split(client: AsyncClient) -> None:
    response = await client.get("/transactions/new")
    assert 'href="/transactions/split"' in response.text


async def test_detail_groups_siblings(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    rows = await list_transactions(session)

    detail = await client.get(f"/transactions/{rows[0].id}")
    assert "Part of one order" in detail.text
    assert "Order total" in detail.text
    assert "$100.00" in detail.text
    # the sibling is linked, the current row is marked instead
    assert f'href="/transactions/{rows[1].id}"' in detail.text
    assert "this one" in detail.text


async def test_detail_hides_grouping_for_single_transactions(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(
        "/transactions",
        data={
            "txn_date": "2026-09-04",
            "merchant": "MBTA",
            "category": "Transit",
            "subcategory": "",
            "amount": "2.40",
            "payment_method_id": str(payment_method.id),
            "notes": "",
        },
    )
    txn = (await list_transactions(session))[0]

    detail = await client.get(f"/transactions/{txn.id}")
    assert "Part of one order" not in detail.text


async def test_list_tags_split_rows(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    listing = await client.get("/transactions", params={"month": "2026-09"})
    assert ">split<" in listing.text
