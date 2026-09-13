"""Errors raised by the transaction template service."""

from jyyfinhub_spendtracker.core.exceptions import ConflictError, NotFoundError


class TransactionTemplateNotFound(NotFoundError):
    error_code = "transaction_template_not_found"

    def __init__(self, template_id: int) -> None:
        super().__init__(f"Transaction template {template_id} does not exist")
        self.template_id = template_id


class TransactionTemplateNameTaken(ConflictError):
    error_code = "transaction_template_name_taken"

    def __init__(self, name: str) -> None:
        super().__init__(f"A transaction template named {name!r} already exists")
        self.name = name
