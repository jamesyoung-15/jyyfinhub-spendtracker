from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from jyyfinhub_spendtracker.transactions.models import (
    ReimbursementSource,
    ReimbursementStatus,
)

# forbid extra so a typo'd field is a 422 instead of silently ignored
WRITE_CONFIG = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TransactionCreate(BaseModel):
    """Schema for creating a transaction.

    Money crosses the wire as integer cents, matching storage. Converting dollars is the web
    form's job, so no float ever touches an amount.
    """

    model_config = WRITE_CONFIG

    txn_date: date
    merchant: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    subcategory: str | None = Field(default=None, max_length=50)
    amount_cents: int = Field(gt=0)
    payment_method_id: int
    notes: str | None = Field(default=None)
    is_subscription: bool = Field(default=False)


class TransactionUpdate(BaseModel):
    """Every field optional. Services use exclude_unset, so an omitted field is left alone."""

    model_config = WRITE_CONFIG

    txn_date: date | None = Field(default=None)
    merchant: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    subcategory: str | None = Field(default=None, max_length=50)
    amount_cents: int | None = Field(default=None, gt=0)
    payment_method_id: int | None = Field(default=None)
    notes: str | None = Field(default=None)
    is_subscription: bool | None = Field(default=None)


class TransactionRead(BaseModel):
    """Schema for reading a transaction."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    txn_date: date
    merchant: str
    category: str
    subcategory: str | None
    amount_cents: int
    payment_method_id: int
    notes: str | None
    is_subscription: bool
    order_ref: str | None


class ReimbursementCreate(BaseModel):
    """Schema for recording money coming back against a transaction."""

    model_config = WRITE_CONFIG

    source: ReimbursementSource
    amount_cents: int = Field(gt=0)
    status: ReimbursementStatus = Field(default=ReimbursementStatus.EXPECTED)
    received_date: date | None = Field(default=None)
    notes: str | None = Field(default=None)


class ReimbursementUpdate(BaseModel):
    """Every field optional. Services use exclude_unset, so an omitted field is left alone."""

    model_config = WRITE_CONFIG

    source: ReimbursementSource | None = Field(default=None)
    amount_cents: int | None = Field(default=None, gt=0)
    status: ReimbursementStatus | None = Field(default=None)
    received_date: date | None = Field(default=None)
    notes: str | None = Field(default=None)


class ReimbursementRead(BaseModel):
    """Schema for reading a reimbursement."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    source: ReimbursementSource
    amount_cents: int
    status: ReimbursementStatus
    received_date: date | None
    notes: str | None


class SplitAllocation(BaseModel):
    """One category's share of a single purchase."""

    model_config = WRITE_CONFIG

    category: str = Field(min_length=1, max_length=50)
    subcategory: str | None = Field(default=None, max_length=50)
    amount_cents: int = Field(gt=0)
    notes: str | None = Field(default=None)


class TransactionSplitCreate(BaseModel):
    """One purchase recorded as several rows, one per category.

    The order total is not stored: the sum of the allocations is the total by construction.
    """

    model_config = WRITE_CONFIG

    txn_date: date
    merchant: str = Field(min_length=1, max_length=200)
    payment_method_id: int
    is_subscription: bool = Field(default=False)
    # fewer than two rows is just a transaction, so it should go through the normal path
    allocations: list[SplitAllocation] = Field(min_length=2)
