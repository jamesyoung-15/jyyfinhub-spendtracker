from httpx import AsyncClient

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod

BASE = "/api/v1/transactions"


def _body(payment_method: PaymentMethod, **overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "txn_date": "2026-09-03",
        "merchant": "Star Market",
        "category": "Groceries",
        "amount_cents": 4318,
        "payment_method_id": payment_method.id,
    }
    return defaults | overrides


async def test_crud_flow(client: AsyncClient, payment_method: PaymentMethod) -> None:
    created = await client.post(BASE, json=_body(payment_method))
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]

    listed = await client.get(BASE)
    assert [t["merchant"] for t in listed.json()] == ["Star Market"]

    patched = await client.patch(
        f"{BASE}/{transaction_id}", json={"amount_cents": 5000}
    )
    assert patched.json()["amount_cents"] == 5000

    deleted = await client.delete(f"{BASE}/{transaction_id}")
    assert deleted.status_code == 204


async def test_not_found_error_contract(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/999")
    assert response.status_code == 404
    assert response.json()["error_code"] == "transaction_not_found"


async def test_invalid_pair_is_422(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.post(
        BASE, json=_body(payment_method, category="Housing", subcategory="Gym")
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_category_pair"


async def test_zero_amount_rejected(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    """gt=0 in the schema, so this never reaches the database CHECK"""
    response = await client.post(BASE, json=_body(payment_method, amount_cents=0))
    assert response.status_code == 422


async def test_month_filter(client: AsyncClient, payment_method: PaymentMethod) -> None:
    await client.post(BASE, json=_body(payment_method, txn_date="2026-08-31"))
    await client.post(BASE, json=_body(payment_method, txn_date="2026-09-15"))

    hits = await client.get(BASE, params={"month": "2026-09"})
    assert [t["txn_date"] for t in hits.json()] == ["2026-09-15"]


async def test_bad_month_format_rejected(client: AsyncClient) -> None:
    """The query pattern rejects it before the service sees it"""
    response = await client.get(BASE, params={"month": "sept"})
    assert response.status_code == 422
