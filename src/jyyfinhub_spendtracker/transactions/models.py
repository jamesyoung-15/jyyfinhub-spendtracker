"""ORM models for transactions, their splits, and their reimbursements."""

from enum import StrEnum


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
