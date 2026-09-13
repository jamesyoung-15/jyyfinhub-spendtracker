"""Cover the migrations themselves.

The rest of the suite builds its schema with create_all, so a broken migration would not
show up anywhere else. These run alembic for real against a throwaway database.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import make_url

from alembic import command
from jyyfinhub_spendtracker.db.registry import Base
from tests.conftest import TEST_DB_URL

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DB = "spendtracker_migrations_test"


def _admin_engine() -> sa.Engine:
    """CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT."""
    admin_url = make_url(TEST_DB_URL).set(database="postgres")
    return sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")


def _drop_database() -> None:
    with _admin_engine().connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{MIGRATION_DB}" WITH (FORCE)'))


@pytest.fixture
def migration_url() -> Iterator[str]:
    """A database of its own per test, so alembic can create and drop the whole schema.

    Function scoped on purpose: upgrade and downgrade leave the schema in different states,
    and a shared database would make the tests order dependent.
    """
    _drop_database()
    with _admin_engine().connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{MIGRATION_DB}"'))

    yield (
        make_url(TEST_DB_URL)
        .set(database=MIGRATION_DB)
        .render_as_string(hide_password=False)
    )

    _drop_database()


@pytest.fixture
def alembic_config(migration_url: str) -> Config:
    """env.py honours a url that is already set, so this redirects it off the real database."""
    config = Config(PROJECT_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", migration_url.replace("%", "%%"))
    return config


def _table_names(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_builds_every_table(alembic_config: Config, migration_url: str) -> None:
    command.upgrade(alembic_config, "head")

    expected = set(Base.metadata.tables) | {"alembic_version"}
    assert _table_names(migration_url) == expected


def test_migrations_match_the_models(
    alembic_config: Config, migration_url: str
) -> None:
    """The drift check: at head, autogenerate should have nothing left to say.

    Catches a model changed without a migration, and a migration that does not reproduce
    what the model declares.
    """
    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(migration_url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"models and migrations disagree: {diff}"


def test_downgrade_returns_to_an_empty_database(
    alembic_config: Config, migration_url: str
) -> None:
    """A downgrade that does not work is a rollback plan that does not exist."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    assert _table_names(migration_url) == {"alembic_version"}


def test_upgrade_is_repeatable_after_a_downgrade(alembic_config: Config) -> None:
    """Catches a downgrade that leaves a constraint or type behind."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


def test_every_revision_applies_one_at_a_time(alembic_config: Config) -> None:
    """upgrade head runs them in one go, which can hide a revision that only works in a batch."""
    script = ScriptDirectory.from_config(alembic_config)

    for revision in reversed(list(script.walk_revisions())):
        command.upgrade(alembic_config, revision.revision)


def test_data_survives_the_latest_migration(
    alembic_config: Config, migration_url: str
) -> None:
    """The one that matters once real spending is in there.

    Seeds rows at the revision before head, then upgrades. A migration that recreates a
    table rather than altering it, or adds a NOT NULL column with no server default,
    fails here.
    """
    script = ScriptDirectory.from_config(alembic_config)
    head = script.get_current_head()
    assert head is not None
    previous = script.get_revision(head).down_revision
    assert isinstance(previous, str)

    command.upgrade(alembic_config, previous)

    engine = sa.create_engine(migration_url)
    try:
        with engine.begin() as conn:
            card_id = conn.execute(
                sa.text(
                    "INSERT INTO payment_methods (name, kind) VALUES ('Amex Gold', 'credit')"
                    " RETURNING id"
                )
            ).scalar_one()
            conn.execute(
                sa.text(
                    "INSERT INTO transactions"
                    " (txn_date, merchant, category, amount_cents, payment_method_id)"
                    " VALUES (:day, 'Star Market', 'Groceries', 4235, :card)"
                ),
                {"day": date(2026, 9, 3), "card": card_id},
            )

        command.upgrade(alembic_config, "head")

        with engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT merchant, amount_cents, payment_method_id FROM transactions"
                )
            ).one()
    finally:
        engine.dispose()

    assert row == ("Star Market", 4235, card_id)
