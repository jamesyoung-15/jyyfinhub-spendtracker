"""Summary endpoints under /api/v1, including the category breakdown."""

from httpx import AsyncClient

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod

API = "/api/v1/summaries"


async def _spend(
    client: AsyncClient,
    payment_method: PaymentMethod,
    category: str,
    amount_cents: int,
    *,
    subcategory: str | None = None,
    day: str = "2026-09-03",
) -> None:
    await client.post(
        "/api/v1/transactions",
        json={
            "txn_date": day,
            "merchant": "Star Market",
            "category": category,
            "subcategory": subcategory,
            "amount_cents": amount_cents,
            "payment_method_id": payment_method.id,
        },
    )


async def test_monthly_categories(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "Groceries", 7500)
    await _spend(client, payment_method, "Leisure", 8000, subcategory="Hobbies")

    response = await client.get(f"{API}/monthly/2026-09/categories")
    assert response.status_code == 200

    rows = response.json()
    assert [row["category"] for row in rows] == ["Leisure", "Groceries"]
    assert rows[0]["subcategories"][0]["subcategory"] == "Hobbies"


async def test_yearly_categories(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "Groceries", 100, day="2026-03-04")
    await _spend(client, payment_method, "Groceries", 200, day="2026-11-04")

    rows = (await client.get(f"{API}/yearly/2026/categories")).json()
    assert rows[0]["gross_cents"] == 300


async def test_empty_month_is_an_empty_list(client: AsyncClient) -> None:
    response = await client.get(f"{API}/monthly/2026-09/categories")
    assert response.status_code == 200
    assert response.json() == []


async def test_bad_month_format_rejected(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/monthly/2026-9/categories")).status_code == 422


async def test_category_route_is_not_shadowed() -> None:
    """/monthly/{month}/categories must not be swallowed by /monthly/{month}."""
    from jyyfinhub_spendtracker.main import create_app

    paths = create_app().openapi()["paths"]
    assert "get" in paths[f"{API}/monthly/{{month}}/categories"]
    assert "get" in paths[f"{API}/yearly/{{year}}/categories"]
