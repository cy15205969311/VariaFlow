from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


engine = create_async_engine(
    settings.effective_database_url,
    echo=settings.debug,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


def create_null_pool_session_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    worker_engine = create_async_engine(
        settings.effective_database_url,
        echo=settings.debug,
        poolclass=NullPool,
        future=True,
    )
    return (
        worker_engine,
        async_sessionmaker(
            bind=worker_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        ),
    )


async def close_engine() -> None:
    await engine.dispose()
