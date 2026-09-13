"""A retired card has to stay selectable, or old rows cannot be entered or edited.

Filtering the dropdown to is_active blocks backfilling a transaction onto a cancelled card, and
leaves an existing row on one unsaveable because no option matches the stored value.
"""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.payment_methods.models import (
    PaymentMethod,
    PaymentMethodKind,
)
from jyyfinhub_spendtracker.transactions.schemas import TransactionCreate
from jyyfinhub_spendtracker.transactions.service import create_transaction

FORMS = ["/transactions/new", "/transactions/split", "/transaction-templates/new"]


@pytest.fixture
async def retired_card(session: AsyncSession) -> PaymentMethod:
    card = PaymentMethod(
        name="Cancelled Store Card", kind=PaymentMethodKind.CREDIT, is_active=False
    )
    session.add(card)
    await session.flush()
    return card


@pytest.mark.parametrize("page", FORMS)
async def test_forms_offer_retired_cards(
    client: AsyncClient, retired_card: PaymentMethod, page: str
) -> None:
    response = await client.get(page)
    assert f'value="{retired_card.id}"' in response.text


@pytest.mark.parametrize("page", FORMS)
async def test_retired_cards_sit_in_their_own_group(
    client: AsyncClient,
    payment_method: PaymentMethod,
    retired_card: PaymentMethod,
    page: str,
) -> None:
    """Everyday entry should still see active cards first."""
    response = await client.get(page)
    assert '<optgroup label="Retired">' in response.text
    assert response.text.index(f'value="{payment_method.id}"') < response.text.index(
        '<optgroup label="Retired">'
    )


async def test_no_empty_group_without_retired_cards(
    client: AsyncClient, payment_method: PaymentMethod
) -> None:
    response = await client.get("/transactions/new")
    assert "optgroup" not in response.text


async def test_edit_preselects_a_retired_card(
    client: AsyncClient, session: AsyncSession, retired_card: PaymentMethod
) -> None:
    """Without this the select falls back to the blank option and the row cannot be saved."""
    txn = await create_transaction(
        session,
        TransactionCreate(
            txn_date=date(2025, 9, 3),
            merchant="Star Market",
            category="Groceries",
            amount_cents=4235,
            payment_method_id=retired_card.id,
        ),
    )

    response = await client.get(f"/transactions/{txn.id}/edit")
    assert f'value="{retired_card.id}" selected' in response.text.replace("\n", " ")
