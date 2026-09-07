from httpx import AsyncClient

BASE = "/api/v1/payment-methods"


async def test_crud_flow(client: AsyncClient) -> None:
    created = await client.post(BASE, json={"name": "Amex", "kind": "credit"})
    assert created.status_code == 201, created.text
    payment_id = created.json()["id"]

    listed = await client.get(BASE)
    assert [p["name"] for p in listed.json()] == ["Amex"]

    fetched = await client.get(f"{BASE}/{payment_id}")
    assert fetched.json()["kind"] == "credit"

    patched = await client.patch(f"{BASE}/{payment_id}", json={"is_active": False})
    assert patched.json()["is_active"] is False

    deleted = await client.delete(f"{BASE}/{payment_id}")
    assert deleted.status_code == 204


async def test_not_found_uses_error_contract(client: AsyncClient) -> None:
    """SpendTrackerError handler turns domain exceptions into error_code/message"""
    response = await client.get(f"{BASE}/999")
    assert response.status_code == 404
    assert response.json() == {
        "error_code": "payment_method_not_found",
        "message": "Payment method 999 does not exist",
    }


async def test_duplicate_name_is_409(client: AsyncClient) -> None:
    await client.post(BASE, json={"name": "Dup"})
    response = await client.post(BASE, json={"name": "Dup"})
    assert response.status_code == 409
    assert response.json()["error_code"] == "payment_method_name_taken"


async def test_unknown_field_rejected(client: AsyncClient) -> None:
    """extra="forbid" on the write schemas catches typo'd request bodies"""
    response = await client.post(BASE, json={"name": "X", "nickname": "oops"})
    assert response.status_code == 422


async def test_expires_filter(client: AsyncClient) -> None:
    await client.post(BASE, json={"name": "Soon", "expires_on": "2027-01-01"})
    await client.post(BASE, json={"name": "Never"})

    hits = await client.get(BASE, params={"expires_from": "2026-01-01"})
    assert [p["name"] for p in hits.json()] == ["Soon"]

    hits = await client.get(
        BASE, params={"expires_from": "2026-01-01", "include_never_expires": True}
    )
    assert [p["name"] for p in hits.json()] == ["Never", "Soon"]
