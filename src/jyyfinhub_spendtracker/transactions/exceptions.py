"""Errors raised by the transaction service."""

from jyyfinhub_spendtracker.core.exceptions import NotFoundError, ValidationError


class TransactionNotFound(NotFoundError):
    error_code = "transaction_not_found"

    def __init__(self, transaction_id: int) -> None:
        super().__init__(f"Transaction {transaction_id} does not exist")
        self.transaction_id = transaction_id


class ReimbursementNotFound(NotFoundError):
    error_code = "reimbursement_not_found"

    def __init__(self, reimbursement_id: int) -> None:
        super().__init__(f"Reimbursement {reimbursement_id} does not exist")
        self.reimbursement_id = reimbursement_id


class ReimbursementNeedsReceivedDate(ValidationError):
    """A received reimbursement must say when the money actually arrived."""

    error_code = "reimbursement_needs_received_date"

    def __init__(self) -> None:
        super().__init__("A received reimbursement needs a received_date")
