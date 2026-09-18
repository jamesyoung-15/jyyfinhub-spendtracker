from datetime import date

from pydantic import BaseModel, ConfigDict


class MonthlySummary(BaseModel):
    """Spend for one month, netted against reimbursements and compared to the goal."""

    model_config = ConfigDict(from_attributes=True)

    month_start: date
    transaction_count: int
    gross_cents: int
    received_cents: int
    net_cents: int
    # None when no goal was set for the month, which is normal rather than an error
    goal_cents: int | None
    # goal minus net, so positive means under budget
    variance_cents: int | None


class SubcategoryBreakdown(BaseModel):
    """Spend for one subcategory within its parent category."""

    model_config = ConfigDict(from_attributes=True)

    # None for a flat category, or a row where the subcategory was left blank
    subcategory: str | None
    transaction_count: int
    gross_cents: int
    received_cents: int
    net_cents: int


class CategoryBreakdown(BaseModel):
    """Spend for one category over a date range, with its subcategories underneath."""

    model_config = ConfigDict(from_attributes=True)

    category: str
    transaction_count: int
    gross_cents: int
    received_cents: int
    net_cents: int
    subcategories: list[SubcategoryBreakdown]


class YearlySummary(BaseModel):
    """Derived from the months, never stored."""

    model_config = ConfigDict(from_attributes=True)

    year: int
    transaction_count: int
    gross_cents: int
    received_cents: int
    net_cents: int
    goal_cents: int
    variance_cents: int
