from pydantic import BaseModel, ConfigDict, Field

# forbid extra so a typo'd field is a 422 instead of silently ignored
WRITE_CONFIG = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TransactionTemplateCreate(BaseModel):
    """Schema for creating a template. Leave amount_cents unset when the amount varies."""

    model_config = WRITE_CONFIG

    name: str = Field(min_length=1, max_length=100)
    merchant: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    subcategory: str | None = Field(default=None, max_length=50)
    amount_cents: int | None = Field(default=None, gt=0)
    payment_method_id: int
    is_subscription: bool = Field(default=False)
    notes: str | None = Field(default=None)
    is_active: bool = Field(default=True)


class TransactionTemplateUpdate(BaseModel):
    """Every field optional. Services use exclude_unset, so an omitted field is left alone."""

    model_config = WRITE_CONFIG

    name: str | None = Field(default=None, min_length=1, max_length=100)
    merchant: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    subcategory: str | None = Field(default=None, max_length=50)
    amount_cents: int | None = Field(default=None, gt=0)
    payment_method_id: int | None = Field(default=None)
    is_subscription: bool | None = Field(default=None)
    notes: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class TransactionTemplateRead(BaseModel):
    """Schema for reading a template."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    merchant: str
    category: str
    subcategory: str | None
    amount_cents: int | None
    payment_method_id: int
    is_subscription: bool
    notes: str | None
    is_active: bool
