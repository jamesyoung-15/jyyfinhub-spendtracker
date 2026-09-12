from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.payment_methods.service import list_payment_methods

PAGE = "/payment-methods"
VALID = {
    "name": "Discover it",
    "kind": "credit",
    "expires_on": "",
    "notes": "",
    "is_active": "on",
}


async def test_list_page_renders(client: AsyncClient) -> None:
    response = await client.get(PAGE)
    assert response.status_code == 200
    assert "No payment methods yet" in response.text


async def test_list_page_shows_rows(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.get(PAGE)
    assert payment_method.name in response.text


async def test_create_redirects_and_persists(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.post(PAGE, data=VALID)
    assert response.status_code == 303
    assert response.headers["location"] == PAGE

    rows = await list_payment_methods(session)
    assert [r.name for r in rows] == ["Discover it"]


async def test_blank_name_rerenders_form(client: AsyncClient) -> None:
    """A form needs the page back with messages, not the API's 422 JSON"""
    response = await client.post(PAGE, data={**VALID, "name": ""})
    assert response.status_code == 422
    assert 'class="error"' in response.text


async def test_invalid_input_is_preserved(client: AsyncClient) -> None:
    """Whatever they typed comes back, so a bad date does not clear the whole form"""
    response = await client.post(
        PAGE, data={**VALID, "name": "Kept Value", "expires_on": "notadate"}
    )
    assert response.status_code == 422
    assert 'value="Kept Value"' in response.text


async def test_duplicate_name_rerenders_form(client: AsyncClient) -> None:
    await client.post(PAGE, data=VALID)
    response = await client.post(PAGE, data=VALID)
    assert response.status_code == 409
    assert "already exists" in response.text


async def test_blank_optional_becomes_null(
    client: AsyncClient, session: AsyncSession
) -> None:
    """An empty input posts "" which would fail date parsing, so it is normalised to None"""
    await client.post(PAGE, data=VALID)
    row = (await list_payment_methods(session))[0]
    assert row.expires_on is None
    assert row.notes is None


async def test_unchecked_checkbox_means_false(
    client: AsyncClient, session: AsyncSession
) -> None:
    """An unchecked box is absent from the payload entirely, not sent as false"""
    payload = {k: v for k, v in VALID.items() if k != "is_active"}
    await client.post(PAGE, data=payload)
    row = (await list_payment_methods(session))[0]
    assert row.is_active is False


async def test_edit_page_prefills(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.get(f"{PAGE}/{payment_method.id}/edit")
    assert response.status_code == 200
    assert f'value="{payment_method.name}"' in response.text


async def test_missing_card_renders_html_not_json(client: AsyncClient) -> None:
    """Same domain exception, but the browser gets a page and the API gets the contract"""
    page = await client.get(f"{PAGE}/9999/edit")
    assert page.status_code == 404
    assert "<html" in page.text

    api = await client.get("/api/v1/payment-methods/9999")
    assert api.json()["error_code"] == "payment_method_not_found"
