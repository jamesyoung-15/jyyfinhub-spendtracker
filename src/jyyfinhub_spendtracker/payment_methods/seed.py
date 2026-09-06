"""File declares quick starting seed data since transcations require a payment method."""

from typing import NamedTuple

from jyyfinhub_spendtracker.payment_methods.models import PaymentMethodKind


class PaymentMethodSeed(NamedTuple):
    """For creating quick seed data for fresh payment method table"""

    name: str
    kind: PaymentMethodKind


# bootstrap rows for a fresh payment_methods table
PAYMENT_METHOD_SEED: tuple[PaymentMethodSeed, ...] = (
    PaymentMethodSeed("Discover it Cash Back Credit Card", PaymentMethodKind.CREDIT),
    PaymentMethodSeed("Synchrony Premier World Mastercard", PaymentMethodKind.CREDIT),
    PaymentMethodSeed("Synchrony Amazon Prime Store Card", PaymentMethodKind.CREDIT),
    PaymentMethodSeed("Verizon Visa Card", PaymentMethodKind.CREDIT),
    PaymentMethodSeed("Discover Debit Card", PaymentMethodKind.DEBIT),
    PaymentMethodSeed("PayPal Debit Card", PaymentMethodKind.DEBIT),
    PaymentMethodSeed("Discover Checking ACH", PaymentMethodKind.ACH),
    PaymentMethodSeed("Discover Savings ACH", PaymentMethodKind.ACH),
    PaymentMethodSeed("Venmo", PaymentMethodKind.OTHER),
)
