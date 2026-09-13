"""Every model in one place, so Base.metadata is complete.

Base.metadata is populated as a side effect of each model class being defined, so alembic and the
test fixtures must import this module rather than db.base. Miss a model here and autogenerate
writes a migration that drops its table. Guarded by test_all_models_registered.

Re-exported through __all__ so the imports are genuinely used, not noqa'd side effects.
"""

from jyyfinhub_spendtracker.db.base import Base
from jyyfinhub_spendtracker.payment_methods.models import PaymentMethod
from jyyfinhub_spendtracker.transaction_templates.models import TransactionTemplate
from jyyfinhub_spendtracker.transactions.models import Transaction

__all__ = ["Base", "PaymentMethod", "Transaction", "TransactionTemplate"]
