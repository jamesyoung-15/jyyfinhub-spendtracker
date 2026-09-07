from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethodKind

# forbid extra so a typo'd field is a 422 instead of silently ignored
WRITE_CONFIG = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PaymentMethodCreate(BaseModel):
    """Schema for creating a payment method"""

    model_config = WRITE_CONFIG

    name: str = Field(min_length=1, max_length=100)
    kind: PaymentMethodKind = Field(default=PaymentMethodKind.OTHER)
    is_active: bool = Field(default=True)
    expires_on: date | None = Field(default=None)
    notes: str | None = Field(default=None)


class PaymentMethodRead(BaseModel):
    """Schema for reading a payment method"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: PaymentMethodKind
    is_active: bool
    expires_on: date | None
    notes: str | None


class PaymentMethodUpdate(BaseModel):
    """Schema for updating a payment method.

    Every field is optional. Services use `exclude_unset` so an omitted field is left alone while
    an explicit null clears it.
    """

    model_config = WRITE_CONFIG

    name: str | None = Field(default=None, min_length=1, max_length=100)
    kind: PaymentMethodKind | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    expires_on: date | None = Field(default=None)
    notes: str | None = Field(default=None)
