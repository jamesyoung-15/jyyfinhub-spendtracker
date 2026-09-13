"""ORM model for monthly budget goals."""

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from jyyfinhub_spendtracker.db.base import Base


class MonthlyBudgetGoal(Base):
    """One budget goal per month. Yearly goals are derived, never stored."""

    __tablename__ = "monthly_budget_goals"

    # natural key: there is exactly one goal per month, so no surrogate id
    month_start: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    goal_cents: Mapped[int] = mapped_column(sa.Integer)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        sa.CheckConstraint("goal_cents >= 0", name="goal_non_negative"),
        # guards the PK invariant. EXTRACT rather than date_trunc, which is not immutable
        # enough for a CHECK on every Postgres version
        sa.CheckConstraint(
            "EXTRACT(DAY FROM month_start) = 1", name="month_start_is_first"
        ),
    )
