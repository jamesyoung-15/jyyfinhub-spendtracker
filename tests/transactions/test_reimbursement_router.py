from httpx import AsyncClient

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod

TRANSACTIONS = "/api/v1/transactions"
REIMBURSEMENTS = "/api/v1/reimbursements"


async def _transaction_id(client: AsyncClient, payment_method: PaymentMethod) -> int:
    response = await client.post(
        TRANSACTIONS,
        json={
            "txn_date": "2026-09-03",
            "merchant": "Work Trip",
            "category": "Travel",
            "subcategory": "Transport",
            "amount_cents": 40000,
            "payment_method_id": payment_method.id,
        },
    )
    return response.json()["id"]


async def test_crud_flow(client: AsyncClient, payment_method: PaymentMethod) -> None:
    txn_id = await _transaction_id(client, payment_method)

    created = await client.post(
        f"{TRANSACTIONS}/{txn_id}/reimbursements",
        json={"source": "Company", "amount_cents": 40000},
    )
    assert created.status_code == 201, created.text
    claim_id = created.json()["id"]
    assert created.json()["status"] == "expected"

    listed = await client.get(f"{TRANSACTIONS}/{txn_id}/reimbursements")
    assert len(listed.json()) == 1

    received = await client.patch(
        f"{REIMBURSEMENTS}/{claim_id}",
        json={"status": "received", "received_date": "2026-10-15"},
    )
    assert received.json()["status"] == "received"

    deleted = await client.delete(f"{REIMBURSEMENTS}/{claim_id}")
    assert deleted.status_code == 204


async def test_received_without_date_is_422(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    txn_id = await _transaction_id(client, payment_method)
    response = await client.post(
        f"{TRANSACTIONS}/{txn_id}/reimbursements",
        json={"source": "Company", "amount_cents": 100, "status": "received"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "reimbursement_needs_received_date"


async def test_unknown_source_is_422(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    txn_id = await _transaction_id(client, payment_method)
    response = await client.post(
        f"{TRANSACTIONS}/{txn_id}/reimbursements",
        json={"source": "Lottery", "amount_cents": 100},
    )
    assert response.status_code == 422


async def test_refund_is_a_valid_source(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    """Returning an item is recorded as a reimbursement, not a negative transaction"""
    txn_id = await _transaction_id(client, payment_method)
    response = await client.post(
        f"{TRANSACTIONS}/{txn_id}/reimbursements",
        json={
            "source": "Refund",
            "amount_cents": 5000,
            "status": "received",
            "received_date": "2026-09-20",
        },
    )
    assert response.status_code == 201


async def test_missing_transaction_error_contract(client: AsyncClient) -> None:
    response = await client.get(f"{TRANSACTIONS}/999/reimbursements")
    assert response.status_code == 404
    assert response.json()["error_code"] == "transaction_not_found"


async def test_missing_reimbursement_error_contract(client: AsyncClient) -> None:
    response = await client.patch(f"{REIMBURSEMENTS}/999", json={"amount_cents": 1})
    assert response.status_code == 404
    assert response.json()["error_code"] == "reimbursement_not_found"
