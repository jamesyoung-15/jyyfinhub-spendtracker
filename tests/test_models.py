from jyyfinhub_spendtracker.db.registry import Base

EXPECTED_TABLES = {
    "payment_methods",
    "transactions",
    "transaction_templates",
}


def test_all_models_registered() -> None:
    """Base.metadata is populated as a side effect of importing each models module.

    A missing import in db/registry.py means autogenerate sees no such table and writes a
    migration that drops it. This fails loudly instead.
    """
    assert set(Base.metadata.tables) == EXPECTED_TABLES
