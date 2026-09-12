"""ORM models for transactions, their splits, and their reimbursements."""

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from jyyfinhub_spendtracker.db.base import Base

if TYPE_CHECKING:
    # only for the annotation; SQLAlchemy resolves "PaymentMethod" through the registry at
    # mapper configuration time, so there is no import at runtime and no cycle
    from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod


class ReimbursementSource(StrEnum):
    """Where a reimbursement came from."""

    COMPANY = "Company"
    FAMILY = "Family"
    REFUND = "Refund"
    OTHER = "Other"


class ReimbursementStatus(StrEnum):
    """Lifecycle of a reimbursement.

    "Active" means EXPECTED plus RECEIVED. Only RECEIVED counts toward budget math.
    """

    EXPECTED = "expected"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Transaction(Base):
    """One spend row. Every row counts toward the budget, with no exclusion flags."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    txn_date: Mapped[date] = mapped_column(sa.Date, index=True)
    merchant: Mapped[str] = mapped_column(sa.String(200))
    category: Mapped[str] = mapped_column(sa.String(50))
    subcategory: Mapped[str | None] = mapped_column(sa.String(50))
    amount_cents: Mapped[int] = mapped_column(sa.Integer)
    payment_method_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        # RESTRICT so a card with history cannot be deleted out from under its transactions
        sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"),
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)
    is_subscription: Mapped[bool] = mapped_column(
        default=False, server_default=sa.false()
    )
    # set only when one purchase is recorded as several rows; siblings share the value
    order_ref: Mapped[str | None] = mapped_column(sa.String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # lazy="raise" turns a forgotten selectinload into a clear error at the access site,
    # instead of MissingGreenlet from deep inside the async driver
    payment_method: Mapped["PaymentMethod"] = relationship(lazy="raise")

    __table_args__ = (
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.Index("ix_transactions_category_subcategory", "category", "subcategory"),
    )
