"""ORM model for payment methods: the cards, accounts, and services spending is charged to."""

from datetime import date, datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from jyyfinhub_spendtracker.db.base import Base


class PaymentMethodKind(StrEnum):
    """Groups payment methods so credit vs debit vs ACH is queryable."""

    CREDIT = "credit"
    DEBIT = "debit"
    ACH = "ach"
    OTHER = "other"


class PaymentMethod(Base):
    """ORM model for payment methods"""

    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100), unique=True)
    # VARCHAR + CHECK rather than a native Postgres enum, native enums can gain values but
    # never drop or reorder them, so retiring one means a create/migrate/drop-type dance
    kind: Mapped[PaymentMethodKind] = mapped_column(
        sa.Enum(
            PaymentMethodKind,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    expires_on: Mapped[date | None] = mapped_column(sa.Date)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)
