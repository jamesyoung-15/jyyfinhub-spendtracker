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
    # passive_deletes leaves the cascade to the database. without it SQLAlchemy would try to
    # load the collection on delete, which lazy="raise" forbids
    reimbursements: Mapped[list["Reimbursement"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )

    __table_args__ = (
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        sa.Index("ix_transactions_category_subcategory", "category", "subcategory"),
    )


class Reimbursement(Base):
    """Money coming back against a transaction: expense claim, family split, or refund.

    Part of the transaction aggregate, so it lives here rather than in its own package.
    """

    __tablename__ = "reimbursements"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[ReimbursementSource] = mapped_column(
        sa.Enum(
            ReimbursementSource,
            native_enum=False,
            create_constraint=False,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    amount_cents: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[ReimbursementStatus] = mapped_column(
        sa.Enum(
            ReimbursementStatus,
            native_enum=False,
            create_constraint=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ReimbursementStatus.EXPECTED,
        server_default=ReimbursementStatus.EXPECTED.value,
    )
    received_date: Mapped[date | None] = mapped_column(sa.Date, index=True)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    transaction: Mapped["Transaction"] = relationship(
        back_populates="reimbursements", lazy="raise"
    )

    __table_args__ = (
        sa.CheckConstraint("amount_cents > 0", name="amount_positive"),
        # explicit rather than Enum(create_constraint=True): autogenerate cannot see one
        # generated by the Enum type and would drop it on every run
        sa.CheckConstraint(
            sa.column("source").in_([s.value for s in ReimbursementSource]),
            name="source_valid",
        ),
        sa.CheckConstraint(
            sa.column("status").in_([s.value for s in ReimbursementStatus]),
            name="status_valid",
        ),
        # no cap against the transaction amount: over-reimbursement happens and must be
        # recordable. clamping to zero is a reporting rule, applied in summaries
        sa.CheckConstraint(
            "status <> 'received' OR received_date IS NOT NULL",
            name="received_needs_date",
        ),
        sa.Index("ix_reimbursements_transaction_id_status", "transaction_id", "status"),
    )
