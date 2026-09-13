from httpx import AsyncClient

BASE = "/api/v1/goals/monthly"


async def test_put_then_get(client: AsyncClient) -> None:
    created = await client.put(f"{BASE}/2026-09", json={"goal_cents": 250000})
    assert created.status_code == 200, created.text
    assert created.json()["month_start"] == "2026-09-01"

    fetched = await client.get(f"{BASE}/2026-09")
    assert fetched.json()["goal_cents"] == 250000


async def test_put_twice_replaces(client: AsyncClient) -> None:
    await client.put(f"{BASE}/2026-09", json={"goal_cents": 250000})
    second = await client.put(f"{BASE}/2026-09", json={"goal_cents": 300000})

    assert second.status_code == 200
    assert second.json()["goal_cents"] == 300000


async def test_missing_goal_error_contract(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/2026-09")
    assert response.status_code == 404
    assert response.json()["error_code"] == "goal_not_found"


async def test_negative_goal_is_422(client: AsyncClient) -> None:
    response = await client.put(f"{BASE}/2026-09", json={"goal_cents": -1})
    assert response.status_code == 422


async def test_bad_month_format_rejected(client: AsyncClient) -> None:
    """The path pattern rejects it before the service sees it"""
    response = await client.put(f"{BASE}/sept", json={"goal_cents": 1000})
    assert response.status_code == 422


async def test_list_for_year(client: AsyncClient) -> None:
    await client.put(f"{BASE}/2025-12", json={"goal_cents": 100})
    await client.put(f"{BASE}/2026-01", json={"goal_cents": 200})
    await client.put(f"{BASE}/2026-09", json={"goal_cents": 300})

    listed = await client.get(BASE, params={"year": 2026})
    assert [g["month_start"] for g in listed.json()] == ["2026-01-01", "2026-09-01"]
