"""Errors raised by the payment method service."""

from jyyfinhub_spendtracker.core.exceptions import ConflictError, NotFoundError


class PaymentMethodNotFound(NotFoundError):
    error_code = "payment_method_not_found"

    def __init__(self, payment_id: int) -> None:
        super().__init__(f"Payment method {payment_id} does not exist")
        self.payment_id = payment_id


class PaymentMethodNameTaken(ConflictError):
    error_code = "payment_method_name_taken"

    def __init__(self, name: str) -> None:
        super().__init__(f"A payment method named {name!r} already exists")
        self.name = name


class PaymentMethodInUse(ConflictError):
    error_code = "payment_method_in_use"

    def __init__(self, payment_id: int) -> None:
        super().__init__(
            f"Payment method {payment_id} has transactions and cannot be deleted; "
            "set is_active to false instead"
        )
        self.payment_id = payment_id
