from httpx import AsyncClient

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod

BASE = "/api/v1/transaction-templates"


def _body(payment_method: PaymentMethod, **overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "name": "Amazon Prime",
        "merchant": "Amazon",
        "category": "Subscriptions",
        "subcategory": "Entertainment",
        "amount_cents": 1499,
        "payment_method_id": payment_method.id,
        "is_subscription": True,
    }
    return defaults | overrides


async def test_crud_flow(client: AsyncClient, payment_method: PaymentMethod) -> None:
    created = await client.post(BASE, json=_body(payment_method))
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]

    listed = await client.get(BASE)
    assert [t["name"] for t in listed.json()] == ["Amazon Prime"]

    retired = await client.patch(f"{BASE}/{template_id}", json={"is_active": False})
    assert retired.json()["is_active"] is False

    assert (await client.get(BASE, params={"is_active": True})).json() == []

    deleted = await client.delete(f"{BASE}/{template_id}")
    assert deleted.status_code == 204


async def test_not_found_error_contract(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/999")
    assert response.status_code == 404
    assert response.json()["error_code"] == "transaction_template_not_found"


async def test_duplicate_name_is_409(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await client.post(BASE, json=_body(payment_method))
    response = await client.post(BASE, json=_body(payment_method))
    assert response.status_code == 409
    assert response.json()["error_code"] == "transaction_template_name_taken"


async def test_invalid_pair_is_422(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.post(
        BASE, json=_body(payment_method, category="Housing", subcategory="Gym")
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_category_pair"


async def test_variable_amount_allowed(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.post(BASE, json=_body(payment_method, amount_cents=None))
    assert response.status_code == 201
    assert response.json()["amount_cents"] is None
