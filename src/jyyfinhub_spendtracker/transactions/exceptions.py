"""Errors raised by the transaction service."""

from jyyfinhub_spendtracker.core.exceptions import NotFoundError, ValidationError


class TransactionNotFound(NotFoundError):
    error_code = "transaction_not_found"

    def __init__(self, transaction_id: int) -> None:
        super().__init__(f"Transaction {transaction_id} does not exist")
        self.transaction_id = transaction_id


class InvalidCategoryPair(ValidationError):
    """A category/subcategory combination that is not in SPEND_CATEGORIES."""

    error_code = "invalid_category_pair"

    def __init__(self, category: str, subcategory: str | None) -> None:
        super().__init__(
            f"{category!r} with subcategory {subcategory!r} is not a valid combination"
        )
        self.category = category
        self.subcategory = subcategory
