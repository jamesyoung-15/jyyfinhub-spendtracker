"""ORM model for transaction templates: saved field presets for the entry form."""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from jyyfinhub_spendtracker.db.base import Base

if TYPE_CHECKING:
    from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod


class TransactionTemplate(Base):
    """A preset that pre-fills the entry form.

    No foreign key either direction between this and transactions: a template fills in a form and
    nothing more, so editing one never rewrites history. Nothing is ever created automatically.
    """

    __tablename__ = "transaction_templates"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100), unique=True)
    merchant: Mapped[str] = mapped_column(sa.String(200))
    category: Mapped[str] = mapped_column(sa.String(50))
    subcategory: Mapped[str | None] = mapped_column(sa.String(50))
    # NULL means the amount varies, so the form leaves it blank to be typed
    amount_cents: Mapped[int | None] = mapped_column(sa.Integer)
    payment_method_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"),
        index=True,
    )
    is_subscription: Mapped[bool] = mapped_column(
        default=False, server_default=sa.false()
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)
    # retires a template without deleting it, for a cancelled subscription
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    payment_method: Mapped["PaymentMethod"] = relationship(lazy="raise")

    __table_args__ = (
        sa.CheckConstraint(
            "amount_cents IS NULL OR amount_cents > 0", name="amount_positive_or_null"
        ),
    )
