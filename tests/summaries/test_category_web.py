"""The breakdown table on the summary page."""

from httpx import AsyncClient

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod

PAGE = "/summary"
SEPTEMBER = "2026-09"


async def _spend(
    client: AsyncClient,
    payment_method: PaymentMethod,
    category: str,
    amount: str,
    *,
    subcategory: str = "",
    day: str = "2026-09-03",
) -> None:
    await client.post(
        "/transactions",
        data={
            "txn_date": day,
            "merchant": "Star Market",
            "category": category,
            "subcategory": subcategory,
            "amount": amount,
            "payment_method_id": str(payment_method.id),
            "notes": "",
        },
    )


async def test_empty_month_says_so(client: AsyncClient) -> None:
    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "Where it went" in page.text
    assert "Nothing recorded." in page.text


async def test_categories_listed_with_totals(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "Groceries", "75.00")
    await _spend(client, payment_method, "Transit", "2.40")

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "Groceries" in page.text
    assert "$75.00" in page.text
    assert "$77.40" in page.text  # footer total


async def test_flat_category_has_no_child_row(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    """Groceries has no subcategories, so a child row would just repeat the parent."""
    await _spend(client, payment_method, "Groceries", "75.00")

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "sub-row" not in page.text


async def test_subcategories_render_as_child_rows(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "Leisure", "80.00", subcategory="Hobbies")
    await _spend(client, payment_method, "Leisure", "30.00", subcategory="Gaming")

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "sub-row" in page.text
    assert "Hobbies" in page.text
    assert "Gaming" in page.text


async def test_unspecified_subcategory_labelled(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    """A row left blank inside a category that has subcategories still needs a name."""
    await _spend(client, payment_method, "Leisure", "80.00", subcategory="Hobbies")
    await _spend(client, payment_method, "Leisure", "10.00")

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "Unspecified" in page.text


async def test_year_breakdown_is_collapsed(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    """A details element keeps the page short without needing JS."""
    await _spend(client, payment_method, "Groceries", "75.00")

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "<details" in page.text
    assert "Where it went in 2026" in page.text


async def test_year_breakdown_spans_other_months(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "Groceries", "75.00", day="2026-03-04")

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    # September is empty, so the figure can only come from the yearly table
    assert "Nothing recorded." in page.text
    assert "$75.00" in page.text
