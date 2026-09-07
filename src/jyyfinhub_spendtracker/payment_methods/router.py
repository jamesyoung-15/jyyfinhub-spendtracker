from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.payment_methods.models import (
    PaymentMethod,
    PaymentMethodKind,
)
from jyyfinhub_spendtracker.payment_methods.schemas import (
    PaymentMethodCreate,
    PaymentMethodRead,
    PaymentMethodUpdate,
)
from jyyfinhub_spendtracker.payment_methods.service import (
    create_payment_method,
    delete_payment_method,
    get_payment_method,
    list_payment_methods,
    update_payment_method,
)

router = APIRouter(prefix="/payment-methods", tags=["payment_methods"])

# routes return ORM objects; response_model does the conversion via from_attributes


@router.get("", response_model=list[PaymentMethodRead])
async def read_payment_methods(
    session: SessionDep,
    kind: PaymentMethodKind | None = None,
    is_active: bool | None = None,
    expires_from: date | None = None,
    expires_before: date | None = None,
    include_never_expires: Annotated[
        bool,
        Query(description="Include cards with no expiry when filtering by date"),
    ] = False,
) -> Sequence[PaymentMethod]:
    return await list_payment_methods(
        session,
        kind=kind,
        is_active=is_active,
        expires_from=expires_from,
        expires_before=expires_before,
        include_never_expires=include_never_expires,
    )


@router.post("", response_model=PaymentMethodRead, status_code=status.HTTP_201_CREATED)
async def add_payment_method(
    session: SessionDep, data: PaymentMethodCreate
) -> PaymentMethod:
    payment_method = await create_payment_method(session, data)
    # handlers own the commit, so the response is only sent once the write is durable
    await session.commit()
    return payment_method


@router.get("/{payment_id}", response_model=PaymentMethodRead)
async def read_payment_method(session: SessionDep, payment_id: int) -> PaymentMethod:
    return await get_payment_method(session, payment_id)


@router.patch("/{payment_id}", response_model=PaymentMethodRead)
async def edit_payment_method(
    session: SessionDep, payment_id: int, data: PaymentMethodUpdate
) -> PaymentMethod:
    """Set is_active to false here to retire a card rather than deleting it"""
    payment_method = await update_payment_method(session, payment_id, data)
    await session.commit()
    return payment_method


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_payment_method(session: SessionDep, payment_id: int) -> None:
    """Only possible for a card with no transactions, otherwise 409"""
    await delete_payment_method(session, payment_id)
    await session.commit()
