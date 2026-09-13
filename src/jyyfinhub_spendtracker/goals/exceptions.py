"""Errors raised by the goal service."""

from datetime import date

from jyyfinhub_spendtracker.core.exceptions import NotFoundError


class GoalNotFound(NotFoundError):
    error_code = "goal_not_found"

    def __init__(self, month_start: date) -> None:
        super().__init__(f"No budget goal set for {month_start:%Y-%m}")
        self.month_start = month_start
