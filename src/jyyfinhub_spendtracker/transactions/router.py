from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.transactions.models import Reimbursement, Transaction
from jyyfinhub_spendtracker.transactions.schemas import (
    ReimbursementCreate,
    ReimbursementRead,
    ReimbursementUpdate,
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
)
from jyyfinhub_spendtracker.transactions.service import (
    create_reimbursement,
    create_transaction,
    delete_reimbursement,
    delete_transaction,
    get_transaction,
    list_reimbursements,
    list_transactions,
    update_reimbursement,
    update_transaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

MonthQuery = Annotated[
    str | None,
    Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM", examples=["2026-09"]),
]


@router.get("", response_model=list[TransactionRead])
async def read_transactions(
    session: SessionDep,
    month: MonthQuery = None,
    year: int | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    order_ref: str | None = None,
) -> Sequence[Transaction]:
    # the pattern above guarantees this parses, so the service takes a real date
    month_date = date.fromisoformat(f"{month}-01") if month else None
    return await list_transactions(
        session,
        month=month_date,
        year=year,
        category=category,
        subcategory=subcategory,
        order_ref=order_ref,
    )


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def add_transaction(session: SessionDep, data: TransactionCreate) -> Transaction:
    transaction = await create_transaction(session, data)
    await session.commit()
    return transaction


@router.get("/{transaction_id}", response_model=TransactionRead)
async def read_transaction(session: SessionDep, transaction_id: int) -> Transaction:
    return await get_transaction(session, transaction_id)


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def edit_transaction(
    session: SessionDep, transaction_id: int, data: TransactionUpdate
) -> Transaction:
    transaction = await update_transaction(session, transaction_id, data)
    await session.commit()
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_transaction(session: SessionDep, transaction_id: int) -> None:
    await delete_transaction(session, transaction_id)
    await session.commit()


reimbursement_router = APIRouter(prefix="/reimbursements", tags=["reimbursements"])


@router.get("/{transaction_id}/reimbursements", response_model=list[ReimbursementRead])
async def read_reimbursements(
    session: SessionDep, transaction_id: int
) -> Sequence[Reimbursement]:
    return await list_reimbursements(session, transaction_id)


@router.post(
    "/{transaction_id}/reimbursements",
    response_model=ReimbursementRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_reimbursement(
    session: SessionDep, transaction_id: int, data: ReimbursementCreate
) -> Reimbursement:
    reimbursement = await create_reimbursement(session, transaction_id, data)
    await session.commit()
    return reimbursement


@reimbursement_router.patch("/{reimbursement_id}", response_model=ReimbursementRead)
async def edit_reimbursement(
    session: SessionDep, reimbursement_id: int, data: ReimbursementUpdate
) -> Reimbursement:
    reimbursement = await update_reimbursement(session, reimbursement_id, data)
    await session.commit()
    return reimbursement


@reimbursement_router.delete(
    "/{reimbursement_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_reimbursement(session: SessionDep, reimbursement_id: int) -> None:
    await delete_reimbursement(session, reimbursement_id)
    await session.commit()
