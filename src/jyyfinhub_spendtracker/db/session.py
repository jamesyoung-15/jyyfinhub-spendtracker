from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from jyyfinhub_spendtracker.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    url=settings.database_url,
    pool_size=settings.sqlalchemy_pool_size,
    max_overflow=settings.sqlalchemy_max_overflow,
    # revalidates a pooled connection before use, so a Postgres restart is not a request error
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """One session per request. Closing rolls back anything uncommitted.

    Deliberately does NOT commit: dependency teardown runs after the response is sent, so a client
    could read back its own write before it landed. Handlers commit instead, which keeps one
    request as one transaction while guaranteeing durability before the response goes out.
    """
    async with SessionLocal() as session:
        yield session
