from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transaction_templates.service import list_templates

PAGE = "/transaction-templates"
NEW_TRANSACTION = "/transactions/new"


def _form(payment_method: PaymentMethod, **overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "name": "Amazon Prime",
        "merchant": "Amazon",
        "category": "Subscriptions",
        "subcategory": "Entertainment",
        "amount": "14.99",
        "payment_method_id": str(payment_method.id),
        "notes": "",
        "is_subscription": "on",
        "is_active": "on",
    }
    return defaults | overrides


async def test_list_page_renders_empty(client: AsyncClient) -> None:
    response = await client.get(PAGE)
    assert response.status_code == 200
    assert "No templates yet" in response.text


async def test_create_and_list(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    created = await client.post(PAGE, data=_form(payment_method))
    assert created.status_code == 303

    rows = await list_templates(session)
    assert [(t.name, t.amount_cents) for t in rows] == [("Amazon Prime", 1499)]

    listed = await client.get(PAGE)
    assert "Amazon Prime" in listed.text


async def test_blank_amount_means_varies(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A blank amount is valid for a template, unlike on the transaction form"""
    await client.post(PAGE, data=_form(payment_method, name="Star Market", amount=""))
    assert (await list_templates(session))[0].amount_cents is None

    listed = await client.get(PAGE)
    assert "varies" in listed.text


async def test_duplicate_name_rerenders_form(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    response = await client.post(PAGE, data=_form(payment_method))
    assert response.status_code == 409
    assert "already exists" in response.text


async def test_invalid_pair_rerenders_form(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.post(
        PAGE, data=_form(payment_method, category="Housing", subcategory="Gym")
    )
    assert response.status_code == 422
    assert "not a valid combination" in response.text


async def test_chips_show_active_templates_only(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method, name="Active One"))
    retired = _form(payment_method, name="Retired One")
    del retired["is_active"]
    await client.post(PAGE, data=retired)

    form = await client.get(NEW_TRANSACTION)
    assert "Active One" in form.text
    assert "Retired One" not in form.text


async def test_template_prefills_entry_form(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    template_id = (await list_templates(session))[0].id

    form = await client.get(NEW_TRANSACTION, params={"template": template_id})
    assert form.status_code == 200
    assert 'value="Amazon"' in form.text
    assert 'value="14.99"' in form.text
    assert 'value="Subscriptions" selected' in form.text


async def test_variable_template_leaves_amount_blank(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method, name="Groceries", amount=""))
    template_id = (await list_templates(session))[0].id

    form = await client.get(NEW_TRANSACTION, params={"template": template_id})
    assert 'id="amount"' in form.text
    assert 'value="14.99"' not in form.text


async def test_prefill_does_not_create_anything(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    """A template fills a form in; nothing is saved until Save is pressed"""
    from jyyfinhub_spendtracker.transactions.service import list_transactions

    await client.post(PAGE, data=_form(payment_method))
    template_id = (await list_templates(session))[0].id

    await client.get(NEW_TRANSACTION, params={"template": template_id})
    assert await list_transactions(session) == []


async def test_missing_template_is_404(client: AsyncClient) -> None:
    response = await client.get(NEW_TRANSACTION, params={"template": 9999})
    assert response.status_code == 404


async def test_edit_then_delete(
    client: AsyncClient, session: AsyncSession, payment_method: PaymentMethod
) -> None:
    await client.post(PAGE, data=_form(payment_method))
    template_id = (await list_templates(session))[0].id

    edit = await client.get(f"{PAGE}/{template_id}/edit")
    assert 'value="Amazon Prime"' in edit.text

    deleted = await client.post(f"{PAGE}/{template_id}/delete")
    assert deleted.status_code == 303
    assert await list_templates(session) == []
