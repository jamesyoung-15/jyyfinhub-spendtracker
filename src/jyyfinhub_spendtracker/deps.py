from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from jyyfinhub_spendtracker.db.session import get_session

# saves writing `session: Session = Depends(get_session)` in every route
SessionDep = Annotated[Session, Depends(get_session)]
