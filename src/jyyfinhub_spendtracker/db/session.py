from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from jyyfinhub_spendtracker.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    url=settings.database_url,
    pool_size=settings.sqlalchemy_pool_size,
    max_overflow=settings.sqlalchemy_max_overflow,
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """One session per request. Services own their own commit so not placed here"""
    async with SessionLocal() as session:
        yield session
