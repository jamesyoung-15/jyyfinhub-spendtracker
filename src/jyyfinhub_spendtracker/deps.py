from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jyyfinhub_spendtracker.db.session import get_session

# saves writing `session: AsyncSession = Depends(get_session)` in every route
SessionDep = Annotated[AsyncSession, Depends(get_session)]
