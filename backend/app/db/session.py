from collections.abc import AsyncGenerator
from typing import Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import get_settings
from app.core.logging import logger

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """Returns or creates the singleton async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.async_database_url

        engine_kwargs = {
            "echo": settings.db_echo,
            "future": True,
        }

        # PostgreSQL connection pool arguments
        if "postgresql" in url or "asyncpg" in url:
            engine_kwargs.update({
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_pre_ping": True,
            })

        _engine = create_async_engine(url, **engine_kwargs)
        logger.info(f"Database engine initialized for host: {settings.postgres_host}")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns or creates the async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding transactional async database sessions."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Gracefully closes database connection pools on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine connections disposed.")
