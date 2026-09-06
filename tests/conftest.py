import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from jyyfinhub_spendtracker.db.registry import Base
from jyyfinhub_spendtracker.payment_methods.models import (
    PaymentMethod,
    PaymentMethodKind,
)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://test:test@127.0.0.1:55432/spendtracker_test",
)


def pytest_configure() -> None:
    """Make DB URL and check to ensure it's a test DB and not prod"""
    # the engine fixture runs drop_all, so a wrong URL here would delete real data
    name = make_url(TEST_DB_URL).database or ""
    if not name.endswith("_test"):
        pytest.exit(f"refusing to run: {name!r} is not a test database", returncode=1)


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    """Creates async engine, drops and re-creates schema per-run"""
    engine = create_async_engine(TEST_DB_URL)

    # registry import above populates Base.metadata; a missing model = a missing table
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Async session factory, use join_transaction_mode to keep test isolated inside a SAVEPOINT"""
    async with engine.connect() as conn:
        # this transaction is owned by the fixture, never by the session
        trans = await conn.begin()
        factory = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            # session gets a SAVEPOINT instead, so its commit() emits RELEASE SAVEPOINT,
            # and its rollback() unwinds to the savepoint rather than killing trans
            join_transaction_mode="create_savepoint",
        )
        async with factory() as s:
            yield s
        # discards everything the test did, including work the session "committed"
        await trans.rollback()


@pytest_asyncio.fixture
async def payment_method(session: AsyncSession) -> PaymentMethod:
    """Payment method is not nullable FK so seed and return id"""
    pm = PaymentMethod(name="Test Card", kind=PaymentMethodKind.CREDIT)
    session.add(pm)
    await session.flush()  # flush for generated id
    return pm
