from collections.abc import Sequence

from fastapi import APIRouter, status

from jyyfinhub_spendtracker.deps import SessionDep
from jyyfinhub_spendtracker.transaction_templates.models import TransactionTemplate
from jyyfinhub_spendtracker.transaction_templates.schemas import (
    TransactionTemplateCreate,
    TransactionTemplateRead,
    TransactionTemplateUpdate,
)
from jyyfinhub_spendtracker.transaction_templates.service import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)

router = APIRouter(prefix="/transaction-templates", tags=["transaction_templates"])


@router.get("", response_model=list[TransactionTemplateRead])
async def read_templates(
    session: SessionDep, is_active: bool | None = None
) -> Sequence[TransactionTemplate]:
    return await list_templates(session, is_active=is_active)


@router.post(
    "", response_model=TransactionTemplateRead, status_code=status.HTTP_201_CREATED
)
async def add_template(
    session: SessionDep, data: TransactionTemplateCreate
) -> TransactionTemplate:
    template = await create_template(session, data)
    await session.commit()
    return template


@router.get("/{template_id}", response_model=TransactionTemplateRead)
async def read_template(session: SessionDep, template_id: int) -> TransactionTemplate:
    return await get_template(session, template_id)


@router.patch("/{template_id}", response_model=TransactionTemplateRead)
async def edit_template(
    session: SessionDep, template_id: int, data: TransactionTemplateUpdate
) -> TransactionTemplate:
    """Set is_active to false here to retire a template rather than deleting it."""
    template = await update_template(session, template_id, data)
    await session.commit()
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_template(session: SessionDep, template_id: int) -> None:
    await delete_template(session, template_id)
    await session.commit()
