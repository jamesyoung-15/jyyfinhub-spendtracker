from datetime import date

from pydantic import BaseModel, ConfigDict, Field

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
