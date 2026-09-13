from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.goals.service import find_goal
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod

PAGE = "/summary"
SEPTEMBER = "2026-09"


async def _spend(
    client: AsyncClient, payment_method: PaymentMethod, amount: str
) -> None:
    await client.post(
        "/transactions",
        data={
            "txn_date": "2026-09-03",
            "merchant": "Star Market",
            "category": "Groceries",
            "subcategory": "",
            "amount": amount,
            "payment_method_id": str(payment_method.id),
            "notes": "",
        },
    )


async def test_page_renders_without_a_goal(client: AsyncClient) -> None:
    response = await client.get(PAGE, params={"month": SEPTEMBER})
    assert response.status_code == 200
    assert "not set" in response.text
    assert "Set a goal below" in response.text


async def test_set_goal_converts_dollars(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.post(f"{PAGE}/{SEPTEMBER}/goal", data={"goal": "2500.00"})
    assert response.status_code == 303

    goal = await find_goal(session, date(2026, 9, 1))
    assert goal is not None
    assert goal.goal_cents == 250000


async def test_variance_shows_under_budget(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "1500.00")
    await client.post(f"{PAGE}/{SEPTEMBER}/goal", data={"goal": "2500.00"})

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "$1000.00" in page.text
    assert "Under budget" in page.text
    assert 'class="under"' in page.text


async def test_variance_shows_over_budget(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "3000.00")
    await client.post(f"{PAGE}/{SEPTEMBER}/goal", data={"goal": "2500.00"})

    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert "Over budget" in page.text
    assert 'class="over"' in page.text
    assert "-$500.00" in page.text


async def test_goal_form_prefills_existing(client: AsyncClient) -> None:
    await client.post(f"{PAGE}/{SEPTEMBER}/goal", data={"goal": "2500.00"})
    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert 'value="2500.00"' in page.text


async def test_negative_goal_rerenders(client: AsyncClient) -> None:
    response = await client.post(f"{PAGE}/{SEPTEMBER}/goal", data={"goal": "-5"})
    assert response.status_code == 422
    assert 'class="error"' in response.text


async def test_month_table_links_to_other_months(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await _spend(client, payment_method, "10.00")
    page = await client.get(PAGE, params={"month": SEPTEMBER})
    assert 'href="/summary?month=2026-09"' in page.text
