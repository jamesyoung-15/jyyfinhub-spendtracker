from datetime import date

from pydantic import BaseModel, ConfigDict, Field

# forbid extra so a typo'd field is a 422 instead of silently ignored
WRITE_CONFIG = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MonthlyBudgetGoalUpsert(BaseModel):
    """Body for PUT. The month comes from the path, not the body."""

    model_config = WRITE_CONFIG

    goal_cents: int = Field(ge=0)
    notes: str | None = Field(default=None)


class MonthlyBudgetGoalRead(BaseModel):
    """Schema for reading a goal."""

    model_config = ConfigDict(from_attributes=True)

    month_start: date
    goal_cents: int
    notes: str | None
