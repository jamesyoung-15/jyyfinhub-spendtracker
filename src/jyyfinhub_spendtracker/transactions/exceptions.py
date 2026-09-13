"""Errors raised by the transaction service."""

from jyyfinhub_spendtracker.core.exceptions import NotFoundError


class TransactionNotFound(NotFoundError):
    error_code = "transaction_not_found"

    def __init__(self, transaction_id: int) -> None:
        super().__init__(f"Transaction {transaction_id} does not exist")
        self.transaction_id = transaction_id
